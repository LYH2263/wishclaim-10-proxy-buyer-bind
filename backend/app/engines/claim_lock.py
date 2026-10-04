"""Claim mutex + TTL release for wishes.

锁记录含分轨的 claimer 与 buyer；任何锁的释放/重置（TTL 超时、过期后被
他人重新认领）都会把 buyer 一并清空 —— 与手动 release、transfer 三路一致。
"""
from datetime import datetime, timedelta, timezone

def parse_ts(s: str) -> datetime:
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def claim_allowed(status: str, claimer: str | None, now: datetime, expires_at: str | None) -> dict:
    """Only open wishes (or expired locks) can be claimed."""
    if status == "fulfilled":
        return {"ok": False, "reason": "already_fulfilled"}
    if status == "claimed" and claimer:
        if expires_at and parse_ts(expires_at) <= now:
            return {"ok": True, "reason": "ttl_expired_reclaim"}
        return {"ok": False, "reason": "locked"}
    if status in ("open", "released"):
        return {"ok": True, "reason": ""}
    return {"ok": False, "reason": "bad_status"}

def lock_payload(claimer: str, now: datetime, ttl_seconds: int, buyer: str | None = None) -> dict:
    exp = now + timedelta(seconds=ttl_seconds)
    return {
        "status": "claimed",
        "claimer": claimer,
        "buyer": buyer,
        "claimed_at": now.isoformat(),
        "expires_at": exp.isoformat(),
    }

def reset_payload() -> dict:
    """锁回到开放池：人锁字段全部清空，buyer 绝不残留（拍板 3）。"""
    return {"status": "open", "claimer": None, "buyer": None, "claimed_at": None, "expires_at": None}

def release_if_expired(status: str, expires_at: str | None, now: datetime) -> dict | None:
    if status != "claimed" or not expires_at:
        return None
    if parse_ts(expires_at) <= now:
        return reset_payload()
    return None
