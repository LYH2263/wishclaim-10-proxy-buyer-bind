"""门禁轨：核销（fulfill）参与人判定。

拍板 2：claimer、buyer 二人皆可核销；第三人拒绝。
buyer 为空（旧轨）时只有 claimer 可核销。
"""

NOT_PARTICIPANT = "not_a_participant"


def fulfill_guard(actor: str | None, claimer: str | None, buyer: str | None) -> dict:
    """返回 {ok, reason, role}。actor 为空同样拒绝。"""
    if actor is not None:
        actor = actor.strip() or None
    if not actor:
        return {"ok": False, "reason": NOT_PARTICIPANT, "role": None}
    if actor == claimer:
        return {"ok": True, "reason": "", "role": "claimer"}
    if buyer and actor == buyer:
        return {"ok": True, "reason": "", "role": "buyer"}
    return {"ok": False, "reason": NOT_PARTICIPANT, "role": None}
