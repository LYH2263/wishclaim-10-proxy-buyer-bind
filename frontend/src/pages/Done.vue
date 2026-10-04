<template>
  <div class="wall">
    <h1 class="serif">已完成</h1>
    <!-- 核销后仍钉写入时的二人快照（claimer/buyer 字段核销后不再变） -->
    <article v-for="w in rows" :key="w.id" class="card">
      <h3>{{ w.title }}</h3>
      <p class="tag">{{ peopleLine(w) }}</p>
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { peopleLine } from '../people'
const rows = ref([])
onMounted(async () => { rows.value = await api('/done') })
</script>
