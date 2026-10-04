from app.db import connect

def init_db():
    c = connect()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS wishes(
      id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, note TEXT, status TEXT,
      claimer TEXT, buyer TEXT, claimed_at TEXT, expires_at TEXT, data_quality TEXT
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
    """)
    # 旧库迁移：buyer 分轨列（SQLite 无 ADD COLUMN IF NOT EXISTS，按 pragma 幂等补列）
    cols = {r["name"] for r in c.execute("PRAGMA table_info(wishes)")}
    if "buyer" not in cols:
        c.execute("ALTER TABLE wishes ADD COLUMN buyer TEXT")
    if c.execute("SELECT COUNT(*) c FROM wishes").fetchone()["c"] == 0:
        c.executemany(
            "INSERT INTO wishes(title,note,status,claimer,buyer,claimed_at,expires_at,data_quality) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                ("机械键盘", "红轴", "open", None, None, None, None, "clean"),
                ("围巾", "羊毛", "open", None, None, None, None, "clean"),
                ("脏愿望-空标题", "", "open", None, None, None, None, "dirty"),
                ("过期锁样例", "应被TTL释放", "claimed", "ghost", None,
                 "2020-01-01T00:00:00+00:00", "2020-01-01T01:00:00+00:00", "dirty"),
            ],
        )
        c.execute("INSERT INTO settings(key,value) VALUES ('ttl_seconds','86400')")
        c.execute("INSERT INTO settings(key,value) VALUES ('wall_title','暖粉愿望墙')")
        c.commit()
    c.close()
