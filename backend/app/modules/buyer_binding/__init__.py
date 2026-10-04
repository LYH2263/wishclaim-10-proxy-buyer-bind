"""Buyer binding 分轨：认领时可绑定 buyer（代买人），与 claimer 分字段。

三个拍板决策（需求方已定）：
1. buyer 与 claimer 不可为同一人；
2. fulfill 允许 claimer 或 buyer 任一人核销，第三人拒绝；
3. release / 转让 / TTL 超时释放后 buyer 一律清空（三路一致）。

子模块：binding（绑定校验）/ guard（核销门禁）/ projection（读模型投影）。
"""
from app.modules.buyer_binding.binding import DIRTY, SAME, bind_check, classify_buyer
from app.modules.buyer_binding.guard import NOT_PARTICIPANT, fulfill_guard
from app.modules.buyer_binding.projection import buyer_slot, people_line, project

__all__ = [
    "DIRTY",
    "SAME",
    "NOT_PARTICIPANT",
    "classify_buyer",
    "bind_check",
    "fulfill_guard",
    "buyer_slot",
    "people_line",
    "project",
]
