"""投影轨：把持久化的 claimer/buyer 分字段钉成前端读模型。

墙卡 / 详情 / 我的认领 / 已完成页共用同一套二人投影：
- buyer 空则退回改造前仅显示 claimer；
- fulfilled 行的 people 是写入时的二人快照（核销后字段不再变）。
"""


def buyer_slot(buyer: str | None) -> str | None:
    """buyer 展示槽：仅做 trim 兜底；数据库里存的已经是 trim 后的值。"""
    if buyer is None:
        return None
    b = buyer.strip()
    return b or None


_slot = buyer_slot


def people_line(claimer: str | None, buyer: str | None) -> str:
    """一行式呈现：'alice / 代买 bob'，无 buyer 时仅 'alice'（或 '—'）。"""
    who = claimer or "—"
    b = _slot(buyer)
    if not b:
        return who
    return f"{who} / 代买 {b}"


def project(row: dict) -> dict:
    """在原始行上补 people（frontends 同时仍可拿独立的 claimer/buyer 字段）。"""
    out = dict(row)
    out["people"] = people_line(row.get("claimer"), row.get("buyer"))
    return out
