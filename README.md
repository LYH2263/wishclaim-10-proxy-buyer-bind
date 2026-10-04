# Wishclaim · 礼物愿望认领

发布 → 认领锁定（互斥+TTL，可绑代买人）→ 核销/释放/转让。

| 服务 | 端口 |
| --- | --- |
| 前端 | 5200 |
| API | 10200 |

```bash
docker compose up --build
pytest backend/app/tests
```

## 代买人分轨（buyer binding）

认领时 `claimer`（认领人）与可选 `buyer`（代买人）**分字段存储**；不传
`buyer` 时完全退回改造前仅 claimer 的行为。列表/详情/我的/已完成的读模型
统一投影为 `people`（buyer 空则只显示 claimer）。

拍板规则：

1. **buyer 不得与 claimer 为同一人** → `409 buyer_same_as_claimer`；
   纯空白 buyer 属脏数据，认领失败 `400 dirty_buyer`（不静默回退）。
2. **fulfill 二人皆可**：claimer 或 buyer 都能核销；第三人 `403
   not_a_participant`。前端按钮禁用态与该错误同钉（`people.js` 镜像后端门禁）。
3. **release / transfer / TTL 超时三路一致，buyer 一律清空**，退回开放池不残留。

`POST /api/wishes/{id}/transfer`（body `{"claimer": "新人"}`）为锁转让：
换新 claimer、TTL 续期、buyer 清空。核销后 `claimer/buyer` 字段不再变动，
已完成页钉的是写入时的二人快照。`/api/mine?claimer=` 同时匹配认领人与代买人。

模块划分：`app/modules/buyer_binding/` 下 `binding`（绑定校验）、
`guard`（核销门禁）、`projection`（读模型投影）；互斥/TTL 仍在
`app/engines/claim_lock.py`。

0-1：`wish_comment` / `secret_santa` / `price_cap`。
