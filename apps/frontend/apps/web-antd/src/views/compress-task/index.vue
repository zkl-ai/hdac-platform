<script setup lang="ts">
import { ref, onMounted, onActivated, computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Card, Row, Col, Input, Select, Button, Table, Tag, Modal, Form, FormItem, InputNumber, Space, Progress, Divider, Popconfirm, message, Statistic } from 'ant-design-vue'
import { ThunderboltOutlined, FolderOpenOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'
import StatCard from '#/components/stat-card.vue'
import InlineMetrics from '#/components/inline-metrics.vue'
import TaskStatusDrawer from './TaskStatusDrawer.vue'
import StartCompressModal from './StartCompressModal.vue'

import 'ant-design-vue/es/card/style'
import 'ant-design-vue/es/row/style'
import 'ant-design-vue/es/col/style'
import 'ant-design-vue/es/input/style'
import 'ant-design-vue/es/select/style'
import 'ant-design-vue/es/button/style'
import 'ant-design-vue/es/table/style'
import 'ant-design-vue/es/tag/style'
import 'ant-design-vue/es/modal/style'
import 'ant-design-vue/es/form/style'
import 'ant-design-vue/es/input-number/style'
import 'ant-design-vue/es/progress/style'
import 'ant-design-vue/es/popconfirm/style'
import 'ant-design-vue/es/statistic/style'

type PhaseType = 'pruning' | 'finetune'
type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const modelFilter = ref('')
const deviceFilter = ref('')
const statusFilter = ref<TaskStatus[]>([])
const modelOptions = ref<string[]>([])
const deviceOptions = ref<string[]>([])

async function loadModels() {
  try {
    const res = await fetch('/api/models/tree')
    const json = await res.json()
    const items = json?.data?.items || json?.items || []
    
    // Filter to match Model Library visibility logic:
    // Only show models that have at least one device node with performance records (grandchildren)
    const visibleItems = items.filter((m: any) => {
      if (!m.children || m.children.length === 0) return false
      return m.children.some((d: any) => d.children && d.children.length > 0)
    })

    const names = visibleItems.map((m: any) => m.name).filter(Boolean)
    modelOptions.value = Array.from(new Set(names))
  } catch {}
}

async function loadDevices() {
  try {
    const res = await fetch('/api/devices/metrics')
    const json = await res.json()
    const items = json?.data?.items || json?.items || []
    const types = items.map((d: any) => d.type).filter(Boolean)
    deviceOptions.value = Array.from(new Set(types))
  } catch {}
}

const summary = ref({
  total: 0,
  running: 0,
  pending: 0,
  succeeded: 0,
  failed: 0,
  stageTotal: 0,
  pruningTotal: 0,
  finetuneTotal: 0,
  pruningRunning: 0,
  finetuneRunning: 0,
})

async function loadSummary() {
  try {
    const res = await fetch('/api/compress/tasks/summary')
    const json = await res.json()
    const data = json?.data || json
    if (data) summary.value = data
  } catch {}
}

const createModalRef = ref()

function onCreate() {
  createModalRef.value?.show()
}

type CompressStage = {
  id: number | string
  phase: PhaseType
  status: TaskStatus
  progress: number
  compressionAlgo?: string
  evalMetric?: string
  latencyBudget?: number | null
  accuracyLossLimit?: number | null
}

type CompressTask = {
  id: number | string
  name: string
  modelName: string
  deviceType?: string
  createdBy?: string
  createdAt?: string
  status: TaskStatus
  stages: CompressStage[]
}

const rawTasks = ref<CompressTask[]>([])
const loading = ref(false)

async function loadTasks() {
  try {
    loading.value = true
    const qs: string[] = []
    if (keyword.value) qs.push('keyword=' + encodeURIComponent(keyword.value))
    if (modelFilter.value) qs.push('modelName=' + encodeURIComponent(modelFilter.value))
    if (deviceFilter.value) qs.push('deviceType=' + encodeURIComponent(deviceFilter.value))
    
    if (statusFilter.value && statusFilter.value.length > 0) {
      statusFilter.value.forEach(s => qs.push('status=' + encodeURIComponent(s)))
    }
    
    const url = qs.length ? `/api/compress/tasks?${qs.join('&')}` : '/api/compress/tasks'
    const res = await fetch(url)
    const json = await res.json()
    const items = json?.data?.items || json?.items || []
    rawTasks.value = items
  } catch {
    rawTasks.value = []
  } finally {
    loading.value = false
  }
}

const tree = computed<any[]>(() => {
  const result: any[] = []
  for (const t of rawTasks.value || []) {
    const stages: CompressStage[] = Array.isArray((t as any).stages) ? (t as any).stages : []
    const firstStage = stages[0] || {}
    
    const top = {
      id: t.id,
      level: 1,
      name: t.name || t.modelName || '任务',
      modelName: t.modelName,
      deviceType: t.deviceType,
      status: t.status,
      createdAt: t.createdAt,
      creator: t.createdBy,
      // Lift params for "View Config"
      compressionAlgo: firstStage.compressionAlgo,
      evalMetric: firstStage.evalMetric,
      algoParams: (firstStage as any).algoParams,
      latencyBudget: firstStage.latencyBudget,
      accuracyLossLimit: firstStage.accuracyLossLimit,
      // Store original stages for "View Status"
      stages: stages
    }
    result.push(top)
  }
  return result
})

function statusTag(status: TaskStatus) {
  const map: Record<TaskStatus, { color: string; text: string }> = {
    pending: { color: 'default', text: '未运行' },
    running: { color: 'processing', text: '运行中' },
    succeeded: { color: 'success', text: '成功' },
    failed: { color: 'error', text: '失败' },
  }
  return map[status] || map.pending
}

const statusDrawerOpen = ref(false)
const selectedTaskId = ref<number | null>(null)
const selectedTaskData = ref<any>(null)

function onViewStatus(record: any) {
  selectedTaskId.value = record.id
  
  // Reconstruct stages structure
  const stages = (record.stages || []).map((c: any) => ({
    id: c.id,
    phase: c.phase,
    status: c.status,
    progress: c.progress,
    compressionAlgo: c.compressionAlgo
  }));
  
  selectedTaskData.value = {
    ...record,
    stages: stages
  }
  statusDrawerOpen.value = true
}

function renderNodeCell(record: any) {
  const showModel = String(record.name || '') !== String(record.modelName || '')
  const created = record.createdAt || ''
  const creator = record.creator || ''
  const st = statusTag(record.status || 'pending')
  
  const isRunning = record.status === 'running'
  const isSucceeded = record.status === 'succeeded'
  
  const runBtn = h(Button, { size: 'small', type: 'primary', disabled: isRunning || isSucceeded, onClick: () => onRunTask(record.id) }, () => '执行')
  const stopBtn = h(Button, { size: 'small', danger: true, disabled: !isRunning, onClick: () => onStopTask(record.id) }, () => '中止')
  // Config button moved to Drawer
  const viewBtn = h(Button, { size: 'small', type: 'primary', ghost: true, onClick: () => onViewStatus(record) }, () => '查看状态')
  const delBtn = h(Popconfirm, { title: '确认删除该任务？', okText: '删除', cancelText: '取消', onConfirm: () => onDeleteTask(record) }, {
    default: () => h(Button, { size: 'small', danger: true }, () => '删除')
  })
  
  return h('div', { class: 'py-2 flex justify-between items-center' }, [
    h('div', { class: 'flex flex-col gap-1' }, [
      h('div', { style: 'font-weight:600;font-size:16px;color:#0f172a;' }, record.name),
      h('div', { style: 'display:flex;gap:10px;align-items:center;color:#64748b;font-size:13px;' }, [
        showModel ? h('span', {}, `模型: ${record.modelName}`) : null,
        record.deviceType ? h(Tag, { color: 'geekblue' }, () => `设备: ${record.deviceType}`) : null,
        h(Tag, { color: st.color }, () => st.text),
        created ? h('span', {}, `创建: ${created}`) : null,
        creator ? h('span', {}, `创建人: ${creator}`) : null,
      ]),
    ]),
    h('div', { style: 'display:flex;gap:8px;' }, [
      runBtn, stopBtn, viewBtn, delBtn
    ]),
  ])
}

const paramsModalVisible = ref(false)
const paramsModalContent = ref('')

function showParams(record: any) {
  const p: any = {}
  if (record.compressionAlgo) p.compressionAlgo = record.compressionAlgo
  if (record.evalMetric) p.evalMetric = record.evalMetric
  if (record.latencyBudget !== undefined && record.latencyBudget !== null) p.latencyBudget = record.latencyBudget
  if (record.accuracyLossLimit !== undefined && record.accuracyLossLimit !== null) p.accuracyLossLimit = record.accuracyLossLimit
  
  if (record.algoParams) {
    try {
      const parsed = JSON.parse(record.algoParams)
      p.algoParams = parsed
    } catch {
      p.algoParams = record.algoParams
    }
  }
  
  paramsModalContent.value = JSON.stringify(p, null, 2)
  paramsModalVisible.value = true
}

const columns = [
  { title: '任务列表', key: 'node', customRender: ({ record }: any) => renderNodeCell(record) },
]

function resetFilters() {
  keyword.value = ''
  modelFilter.value = ''
  deviceFilter.value = ''
  statusFilter.value = []
  loadTasks()
}

function setStatusFilter(statuses: TaskStatus[]) {
  statusFilter.value = statuses
  loadTasks()
}

function checkAction() {
  let action = route.query.action as string
  
  if (!action && history.state?.action) {
    action = history.state.action
  }
  
  if (action === 'create') {
    onCreate()
  } else if (action === 'execute') {
    statusFilter.value = ['pending']
  } else if (action === 'view') {
    // Default view
  }

  // Cleanup to prevent re-triggering
  if (route.query.action) {
    const q = { ...route.query }
    delete q.action
    router.replace({ query: q })
  }
  if (history.state?.action) {
    const s = { ...history.state }
    delete s.action
    history.replaceState(s, '')
  }
}

onMounted(async () => {
  loadModels()
  loadDevices()
  await loadSummary()
  await loadTasks()
  checkAction()
})

onActivated(() => {
  checkAction()
})

async function onStopTask(id: string | number) {
  try {
    const res = await fetch(`/api/compress/tasks/${id}/stop`, {
        method: 'POST'
    })
    const json = await res.json()
    if (json.code === 0) {
        message.success('已请求中止任务')
        loadTasks()
        loadSummary()
    } else {
        message.error(json.message || '中止失败')
    }
  } catch {
    message.error('请求异常')
  }
}
async function onRunTask(id: string | number) {
  try {
    const res = await fetch(`/api/compress/tasks/${id}/start`, {
        method: 'POST'
    })
    const json = await res.json()
    if (json.code === 0) {
        message.success('任务已开始执行')
        loadTasks()
        loadSummary()
    } else {
        message.error(json.message || '启动失败')
    }
  } catch (e) {
    message.error('启动失败')
  }
}

async function onDeleteTask(record: any) {
  try {
    const id = record?.id
    const name = String(record?.name || record?.modelName || '任务')
    
    const res = await fetch(`/api/compress/tasks/${id}`, {
        method: 'DELETE'
    })
    const json = await res.json()
    
    if (json.code === 0) {
        rawTasks.value = (rawTasks.value || []).filter((x) => String((x as any)?.id) !== String(id))
        message.success('已删除任务：' + name)
        loadSummary()
    } else {
        message.error(json.message || '删除失败')
    }
  } catch {
    message.error('删除请求异常')
  }
}

</script>

<template>
  <div class="p-5 compress-page">
    <Card>
      <div class="summary-header">DNN模型压缩任务信息总揽</div>
      <Row :gutter="16">
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-blue-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter([])">
            <Statistic title="全部任务" :value="summary.total" :value-style="{ color: '#1d4ed8' }">
              <template #prefix><FolderOpenOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-indigo-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(['running', 'pending'])">
            <Statistic title="进行中 (运行/排队)" :value="(summary.running || 0) + (summary.pending || 0)" :value-style="{ color: '#4338ca' }">
              <template #prefix><SyncOutlined spin /></template>
              <template #suffix>
                <span class="text-xs text-gray-500 ml-2">运行: {{ summary.running }} / 排队: {{ summary.pending }}</span>
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-green-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(['succeeded'])">
            <Statistic title="已完成" :value="summary.succeeded" :value-style="{ color: '#15803d' }">
              <template #prefix><CheckCircleOutlined /></template>
              <template #suffix>
                 <span class="text-xs text-gray-500 ml-2" v-if="summary.total > 0">
                   {{ Math.round((summary.succeeded / summary.total) * 100) }}%
                 </span>
              </template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-red-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(['failed'])">
            <Statistic title="异常/失败" :value="summary.failed" :value-style="{ color: '#b91c1c' }">
              <template #prefix><CloseCircleOutlined /></template>
            </Statistic>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card style="margin-top:12px">
      <div class="mb-5">
        <Space wrap>
          <Input v-model:value="keyword" placeholder="搜索任务名称" allow-clear style="width:220px" @pressEnter="loadTasks" />
          <Select 
            v-model:value="modelFilter" 
            placeholder="模型名称" 
            allow-clear 
            show-search
            style="width:200px" 
            :options="modelOptions.map(m => ({ label: m, value: m }))"
          />
          <Select 
            v-model:value="deviceFilter" 
            placeholder="设备类型" 
            allow-clear 
            show-search
            style="width:200px" 
            :options="deviceOptions.map(d => ({ label: d, value: d }))"
          />
          <Select v-model:value="statusFilter" mode="multiple" placeholder="状态" allow-clear style="width:240px">
            <Select.Option value="pending">未运行</Select.Option>
            <Select.Option value="running">运行中</Select.Option>
            <Select.Option value="succeeded">成功</Select.Option>
            <Select.Option value="failed">失败</Select.Option>
          </Select>
          <Button type="primary" shape="round" @click="loadTasks">搜索</Button>
          <Button @click="resetFilters">重置</Button>
          <Divider type="vertical" />
          <Button type="default" @click="onCreate">新增</Button>
        </Space>
      </div>
      
      <Table
        :data-source="tree"
        :loading="loading"
        :rowKey="(r:any)=>r.id"
        :pagination="{ pageSize: 8 }"
        :columns="columns"
      />
    </Card>

    <TaskStatusDrawer 
      v-model:open="statusDrawerOpen" 
      :task-id="selectedTaskId" 
      :task-data="selectedTaskData"
    />
    
    <Modal v-model:open="paramsModalVisible" title="任务参数详情" :footer="null" width="600px">
      <pre style="background:#f4f4f5;padding:12px;border-radius:6px;overflow:auto;max-height:500px">{{ paramsModalContent }}</pre>
    </Modal>

    <StartCompressModal ref="createModalRef" @success="loadTasks" />
  </div>
</template>

<style scoped>
.compress-page { display: grid; gap: 8px; }
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.transition-shadow { transition: box-shadow 0.3s; }
.cursor-pointer { cursor: pointer; }
.hover\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
.mb-5 { margin-bottom: 20px; }
</style>
