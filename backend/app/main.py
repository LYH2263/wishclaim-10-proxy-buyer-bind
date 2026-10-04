from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app import seed
from app.db import connect
from app.engines.claim_lock import claim_allowed, lock_payload, release_if_expired
from app.modules.buyer_binding import (
    bind_check,
    classify_buyer,
    fulfill_guard,
    project,
)

app = FastAPI(title="Wishclaim", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup(): seed.init_db()

def now(): return datetime.now(timezone.utc)

def ttl():
    c = connect(); row = c.execute("SELECT value FROM settings WHERE key='ttl_seconds'").fetchone(); c.close()
    return int(row["value"] if row else 86400)

def sweep(c):
    for r in c.execute("SELECT * FROM wishes WHERE status='claimed'"):
        rel = release_if_expired(r["status"], r["expires_at"], now())
        if rel:
            c.execute("UPDATE wishes SET status=?, claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
                      (rel["status"], rel["claimer"], rel["buyer"],
                       rel["claimed_at"], rel["expires_at"], r["id"]))

@app.get("/api/health")
def health(): return {"ok": True, "project": "wishclaim"}

@app.get("/api/wishes")
def list_wishes():
    c = connect(); sweep(c); c.commit()
    rows = [project(dict(r)) for r in c.execute("SELECT * FROM wishes ORDER BY id DESC")]; c.close(); return rows

@app.get("/api/wishes/{wid}")
def get_wish(wid: int):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone(); c.close()
    if not r: raise HTTPException(404, "not found")
    return project(dict(r))

class WishIn(BaseModel):
    title: str
    note: str = ""

@app.post("/api/wishes")
def create_wish(body: WishIn):
    c = connect()
    cur = c.execute("INSERT INTO wishes(title,note,status,data_quality) VALUES (?,?,?,?)",
                    (body.title, body.note, "open", "clean"))
    c.commit(); wid = cur.lastrowid; c.close(); return {"id": wid}

class ClaimIn(BaseModel):
    claimer: str
    buyer: str | None = None

@app.post("/api/wishes/{wid}/claim")
def claim(wid: int, body: ClaimIn):
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    allowed = claim_allowed(r["status"], r["claimer"], now(), r["expires_at"])
    if not allowed["ok"]:
        c.close(); raise HTTPException(409, allowed["reason"])
    claimer = body.claimer.strip()
    buyer, derr = classify_buyer(body.buyer)
    if derr:
        # 脏 buyer：认领必须失败，绝不静默回退仅 claimer
        c.close(); raise HTTPException(400, derr)
    bchk = bind_check(claimer, buyer)
    if not bchk["ok"]:
        # 拍板 1：buyer 与 claimer 不允许为同一人
        c.close(); raise HTTPException(409, bchk["reason"])
    p = lock_payload(claimer, now(), ttl(), buyer)
    c.execute("UPDATE wishes SET status=?, claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
              (p["status"], p["claimer"], p["buyer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

@app.post("/api/wishes/{wid}/release")
def release(wid: int):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    # 拍板 3：release 清空 buyer
    c.execute("UPDATE wishes SET status='released', claimer=NULL, buyer=NULL, "
              "claimed_at=NULL, expires_at=NULL WHERE id=?", (wid,))
    c.commit(); c.close(); return {"ok": True, "status": "released"}

class TransferIn(BaseModel):
    claimer: str

@app.post("/api/wishes/{wid}/transfer")
def transfer(wid: int, body: TransferIn):
    """锁转让：换新 claimer、TTL 续期；拍板 3 —— 旧 buyer 一律清空。"""
    c = connect(); sweep(c); c.commit()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "not_claimed")
    claimer = body.claimer.strip()
    if not claimer:
        c.close(); raise HTTPException(400, "dirty_claimer")
    p = lock_payload(claimer, now(), ttl(), None)
    c.execute("UPDATE wishes SET status=?, claimer=?, buyer=?, claimed_at=?, expires_at=? WHERE id=?",
              (p["status"], p["claimer"], p["buyer"], p["claimed_at"], p["expires_at"], wid))
    c.commit(); c.close(); return p

class FulfillIn(BaseModel):
    actor: str | None = None

@app.post("/api/wishes/{wid}/fulfill")
def fulfill(wid: int, body: FulfillIn):
    c = connect()
    r = c.execute("SELECT * FROM wishes WHERE id=?", (wid,)).fetchone()
    if not r: c.close(); raise HTTPException(404, "not found")
    if r["status"] != "claimed":
        c.close(); raise HTTPException(400, "need_claim")
    # 拍板 2：claimer、buyer 二人皆可核销，第三人拒绝
    guard = fulfill_guard(body.actor, r["claimer"], r["buyer"])
    if not guard["ok"]:
        c.close(); raise HTTPException(403, guard["reason"])
    c.execute("UPDATE wishes SET status='fulfilled' WHERE id=?", (wid,))
    c.commit(); c.close()
    # claimer/buyer 字段原样保留 —— 已完成页钉的是写入时二人快照
    return {"ok": True, "status": "fulfilled", "fulfilled_by": guard["role"]}

@app.get("/api/mine")
def mine(claimer: str):
    # 认领人或代买人都是"我的"：两轨任一命中即返回，投影钉二人
    c = connect(); sweep(c); c.commit()
    rows = [project(dict(r)) for r in c.execute(
        "SELECT * FROM wishes WHERE claimer=? OR buyer=? ORDER BY id DESC", (claimer, claimer))]
    c.close(); return rows

@app.get("/api/done")
def done():
    c = connect()
    rows = [project(dict(r)) for r in c.execute("SELECT * FROM wishes WHERE status='fulfilled'")]
    c.close(); return rows

@app.get("/api/settings")
def settings():
    c = connect(); rows = {r["key"]: r["value"] for r in c.execute("SELECT * FROM settings")}; c.close(); return rows

@app.get("/api/rules")
def rules():
    return {
        "mutex": "同一愿望同时只能被一人认领",
        "ttl": "认领超时未核销则自动释放",
        "buyer": "认领时可绑定代买人 buyer，与认领人分字段；buyer 不得与认领人相同",
        "fulfill": "核销后状态变为 fulfilled；认领人与代买人二人皆可核销，第三人不可",
        "release": "释放或转让后，代买人绑定一并清空",
    }
