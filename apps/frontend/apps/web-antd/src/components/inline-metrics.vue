<template>
  <div class="inline-row">
    <div class="inline-item">
      <span class="inline-label">{{ leftLabel }}</span>
      <span class="inline-value">{{ leftValue }}</span>
    </div>
    <span v-if="showDivider" class="inline-divider">|</span>
    <div class="inline-item right">
      <span class="inline-label">{{ rightLabel }}</span>
      <span class="inline-value">{{ rightValue }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  leftLabel: string
  leftValue: string | number
  rightLabel: string
  rightValue: string | number
  showDivider?: boolean
}>(), { showDivider: true })
</script>

<style scoped>
.inline-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: baseline;
}
.inline-item {
  display: flex;
  justify-content: flex-start;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}
.inline-item.right {
  justify-content: flex-start;
}
.inline-divider { color: #cbd5e1; }
.inline-label { font-size: 15px; color: #475569; }
.inline-value { font-size: 22px; font-weight: 700; color: #0f172a; }
</style>
