"""绑定轨：buyer 归一化与绑定校验。

buyer 缺省（None 或 ""）= 不分轨，退回改造前仅 claimer。
纯空白 buyer（"   "）视为脏数据，认领必须失败，不得静默回退仅 claimer。
"""

# 原因码：端点分别映射为 400 / 409
DIRTY = "dirty_buyer"
SAME = "buyer_same_as_claimer"


def classify_buyer(raw: str | None) -> tuple[str | None, str | None]:
    """把入参 buyer 归一化。

    返回 (buyer, error)：
    - None / ""        -> (None, None)         未绑定，走仅 claimer 旧轨；
    - 纯空白 "   "      -> (None, DIRTY)        脏 buyer，认领必须失败；
    - 否则              -> (trim 后名字, None)。
    """
    if raw is None or raw == "":
        return None, None
    b = raw.strip()
    if not b:
        return None, DIRTY
    return b, None


def bind_check(claimer: str, buyer: str | None) -> dict:
    """绑定门禁：拍板 1 —— buyer 与 claimer 不允许为同一人。"""
    if buyer is None:
        return {"ok": True, "reason": ""}
    if buyer.strip() == claimer.strip():
        return {"ok": False, "reason": SAME}
    return {"ok": True, "reason": ""}
