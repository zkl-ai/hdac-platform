<template>
  <div 
    class="node-card"
    :class="{ 'active': activeScenario === 'compress', 'dimmed': activeScenario && activeScenario !== 'compress' }"
    @click="emit('select', 'compress')"
  >
    <div class="header">
      <CompressOutlined class="header-icon" />
      <span class="header-text">DNN模型压缩</span>
    </div>
    <div class="content">
      <div class="task-buttons">
        <div class="btn-block">
          <Button size="small" shape="round" :type="activeScenario === 'compress' ? 'primary' : 'default'" @click.stop="onCreate">
            <template #icon><PlusOutlined /></template>创建DNN模型压缩任务
          </Button>
        </div>
        <div class="btn-block">
          <Button size="small" shape="round" :type="activeScenario === 'compress' ? 'primary' : 'default'" @click.stop="onRun">
            <template #icon><PlayCircleOutlined /></template>执行DNN模型压缩任务
          </Button>
        </div>
        <div class="btn-block">
          <Button size="small" shape="round" :type="activeScenario === 'compress' ? 'primary' : 'default'" @click.stop="onView">
            <template #icon><DashboardOutlined /></template>查看DNN模型压缩任务状态
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CompressOutlined, PlusOutlined, PlayCircleOutlined, DashboardOutlined } from "@ant-design/icons-vue";
import { Button, message } from 'ant-design-vue'
import { useRouter } from 'vue-router'

defineProps<{
  activeScenario?: string | null
}>()

const emit = defineEmits<{
  (e: 'select', scenario: string): void
  (e: 'create'): void
}>()

const router = useRouter()

const onCreate = () => {
  emit('select', 'compress')
  router.push({ path: '/compress-task', state: { action: 'create' } })
}
const onRun = () => {
  emit('select', 'compress')
  router.push({ path: '/compress-task', state: { action: 'execute' } })
}
const onView = () => {
  emit('select', 'compress')
  router.push({ path: '/compress-task', state: { action: 'view' } })
}
</script>

<style scoped>
.node-card {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  overflow: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #dbeafe;
  border-radius: 14px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 10px;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
  transition: all 0.3s ease;
  cursor: pointer;
}

.node-card.active {
  background: #eff6ff;
  border-color: #2563eb;
  box-shadow: 0 8px 24px rgba(37, 99, 235, 0.2);
}

.node-card.dimmed {
  opacity: 0.6;
  filter: grayscale(0.4);
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 22px;
  color: #2563eb;
}

.header-text {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.content {
  flex: 1;
  display: flex;
}

.task-buttons {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  align-items: stretch;
  width: 100%;
  height: 100%;
}

.btn-block {
  height: 100%;
}

:deep(.ant-btn) {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 16px;
  letter-spacing: 0.2px;
  background: linear-gradient(180deg, #fbfbfd 0%, #f6f7fb 100%);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  color: #1f2937;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.04);
  transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

:deep(.ant-btn:hover) {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-color: #93c5fd;
  color: #2563eb;
  transform: translateY(-1px);
}

:deep(.ant-btn-primary) {
  background: linear-gradient(180deg, #fbfbfd 0%, #f6f7fb 100%);
  border: 1px solid #e5e7eb;
  color: #1f2937;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
}

:deep(.ant-btn-primary:hover) {
  background: linear-gradient(180deg, #eff6ff 0%, #dbeafe 100%);
  border-color: #93c5fd;
  color: #2563eb;
  transform: translateY(-1px);
}
</style>
