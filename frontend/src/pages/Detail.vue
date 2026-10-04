<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <p class="tag">状态 {{ w.status }} · {{ peopleLine(w) }}</p>
    <p v-if="fulfilledHint" class="tag">{{ fulfilledHint }}</p>
    <p v-if="err" class="err">{{ err }}</p>

    <template v-if="w.status !== 'fulfilled'">
      <input v-model="claimer" placeholder="认领人（你的名字）" />
      <input v-model="buyer" placeholder="代买人 buyer（可留空，须与认领人不同）" />
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button @click="claim" :disabled="w.status === 'claimed'">认领锁定</button>
        <button class="ghost" @click="release" :disabled="w.status !== 'claimed'">释放</button>
        <!-- 核销门禁：当前名字必须是 claimer 或 buyer，与后端 403 not_a_participant 同钉 -->
        <button class="ghost" @click="fulfill" :disabled="!canFulfill(claimer, w)">核销完成</button>
        <button class="ghost" @click="transfer" :disabled="w.status !== 'claimed'">转让给我</button>
      </div>
      <p v-if="w.status === 'claimed' && !canFulfill(claimer, w)" class="tag">
        仅认领人或代买人可核销；转让/释放后代买人绑定将清空
      </p>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { canFulfill, peopleLine } from '../people'
const props = defineProps({ id: String })
const w = ref({})
const claimer = ref('访客')
const buyer = ref('')
const err = ref('')
const fulfilledHint = computed(() =>
  w.value.status === 'fulfilled' ? `已完成 · ${peopleLine(w.value)}（二人快照）` : '')
async function load() {
  err.value = ''
  w.value = await api('/wishes/' + props.id)
}
async function claim() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/claim', {
      method: 'POST',
      body: JSON.stringify({ claimer: claimer.value, buyer: buyer.value || null }),
    })
    await load()
  } catch (e) { err.value = friendly(e.message) }
}
async function release() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/release', { method: 'POST', body: '{}' })
    buyer.value = ''
    await load()
  } catch (e) { err.value = friendly(e.message) }
}
async function fulfill() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/fulfill', {
      method: 'POST',
      body: JSON.stringify({ actor: claimer.value }),
    })
    await load()
  } catch (e) { err.value = friendly(e.message) }
}
async function transfer() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/transfer', {
      method: 'POST',
      body: JSON.stringify({ claimer: claimer.value }),
    })
    buyer.value = ''
    await load()
  } catch (e) { err.value = friendly(e.message) }
}
function friendly(msg) {
  if (msg === 'not_a_participant') return '你既不是认领人也不是代买人，无权核销'
  if (msg === 'buyer_same_as_claimer') return '代买人不能与认领人为同一人'
  if (msg === 'dirty_buyer') return '代买人不能是纯空白'
  if (msg === 'locked') return '已被他人锁定'
  return msg
}
onMounted(load)
</script>
