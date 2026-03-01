<template>
  <div :class="['stat-box', variantClass]">
    <div class="stat-header">
      <slot name="icon" />
      <span v-if="showTitle && title" class="stat-title">{{ title }}</span>
      <slot name="header-extra" />
    </div>
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

type Variant = 'primary' | 'purple' | 'green' | 'red'

const props = withDefaults(defineProps<{ title?: string; variant?: Variant; showTitle?: boolean }>(), { showTitle: true })

const variantClass = computed(() => props.variant ? `stat-${props.variant}` : 'stat-primary')
</script>

<style scoped>
.stat-box {
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border: 1px solid #e2e8f0;
  background: #ffffff;
  transition: all .2s;
  width: 100%;
}

.stat-box:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.stat-title {
  font-size: 15px;
  color: #334155;
}

.stat-icon {
  font-size: 18px;
}
.stat-icon.primary { color: #2563eb; }
.stat-icon.purple { color: #7c3aed; }
.stat-icon.green { color: #16a34a; }
.stat-icon.red { color: #dc2626; }

.stat-primary { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 80%); }
.stat-purple { background: linear-gradient(180deg, #f5f3ff 0%, #ffffff 80%); }
.stat-green { background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 80%); }
.stat-red { background: linear-gradient(180deg, #fef2f2 0%, #ffffff 80%); }
</style>
