// 与后端 buyer_binding 投影/门禁同钉的前端镜像。
// 后端已下发 people；本地仅在缺字段时按同一规则兜底。
export function peopleLine(w) {
  if (w.people) return w.people
  const c = (w.claimer || '').trim()
  const b = (w.buyer || '').trim()
  if (!c && !b) return '—'
  return b ? `${c} / 代买 ${b}` : (c || '—')
}

// 拍板 2：fulfill 二人皆可；buyer 空时仅 claimer。按钮态与 403 not_a_participant 同钉。
export function canFulfill(actor, w) {
  const a = (actor || '').trim()
  if (!a || w.status !== 'claimed') return false
  if (a === (w.claimer || '').trim()) return true
  const b = (w.buyer || '').trim()
  return !!b && a === b
}

export const FULFILL_DENY_REASON = 'not_a_participant'
