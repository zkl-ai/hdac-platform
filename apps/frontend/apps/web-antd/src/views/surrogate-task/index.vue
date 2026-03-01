<script setup lang="ts">
import { ref, onMounted, h, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Card, Row, Col, Input, Select, Button, Table, Tag, message, Space, Divider, Popconfirm, Statistic } from 'ant-design-vue'
import dayjs from 'dayjs'
import StartSurrogateModal from './StartSurrogateModal.vue'
import SurrogateStatusDrawer from './SurrogateStatusDrawer.vue'
import { FolderOpenOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'

import 'ant-design-vue/es/card/style'
import 'ant-design-vue/es/row/style'
import 'ant-design-vue/es/col/style'
import 'ant-design-vue/es/input/style'
import 'ant-design-vue/es/select/style'
import 'ant-design-vue/es/button/style'
import 'ant-design-vue/es/table/style'
import 'ant-design-vue/es/tag/style'
import 'ant-design-vue/es/popconfirm/style'
import 'ant-design-vue/es/statistic/style'

type TaskStatus = 'pending' | 'running' | 'succeeded' | 'failed'

const keyword = ref('')
const modelFilter = ref('')
const deviceFilter = ref('')
const statusFilter = ref<TaskStatus[]>([])
const modelOptions = ref<string[]>([])
const deviceOptions = ref<string[]>([])
const route = useRoute()

const summary = ref({ total: 0, running: 0, pending: 0, succeeded: 0, failed: 0 })

// Drawer Control
const drawerOpen = ref(false)
const selectedTask = ref<any>(null)

// Handle Route Query for "View Details"
const handleRouteQuery = () => {
  if (route.query.viewTaskId) {
    const tid = Number(route.query.viewTaskId)
    // Update if task ID changed OR if drawer is currently closed (to allow re-opening same task)
    if (tid && (!selectedTask.value || selectedTask.value.id !== tid || !drawerOpen.value)) {
       selectedTask.value = { id: tid }
       drawerOpen.value = true
    }
  }
}

// Watch for route changes (important for KeepAlive/Tabs)
watch(() => route.query.viewTaskId, (val) => {
    if (val) handleRouteQuery()
}, { immediate: true })

async function loadSummary() {
  try {
    const res = await fetch('/api/surrogate/tasks/summary')
    const json = await res.json()
    const data = json?.data || json
    summary.value = data || summary.value
  } catch {}
}

async function loadModels() {
  try {
    const res = await fetch('/api/models/tree')
    const json = await res.json()
    const items = json?.data?.items || json?.items || []
    
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

const startModalRef = ref()

function onCreate() {
  startModalRef.value?.show()
}

function handleTaskCreated() {
  loadSummary()
  loadPipelines()
}

onMounted(async () => { 
  await loadSummary()
  loadModels()
  loadDevices()
  loadPipelines() // Consolidated loadPipelines here
  
  if (history.state?.action === 'create') {
    onCreate()
    history.replaceState({}, '')
  } else if (history.state?.action === 'execute') {
    statusFilter.value = ['pending']
    await loadPipelines()
    history.replaceState({}, '')
  } else if (history.state?.viewTaskId) {
    // Handle viewTaskId from state (aligned with action='create')
    const tid = Number(history.state.viewTaskId)
    if (tid) {
        selectedTask.value = { id: tid }
        drawerOpen.value = true
    }
    history.replaceState({}, '')
  }
  
  // Check initial route query (Fallback)
  handleRouteQuery()
})

const pipeList = ref<any[]>([])
const pipeLoading = ref(false)

async function loadPipelines() {
    try {
      pipeLoading.value = true
      let url = '/api/surrogate/pipelines'
      const params = new URLSearchParams()
      if (keyword.value) params.append('keyword', keyword.value)
      if (modelFilter.value) params.append('modelName', modelFilter.value)
      if (deviceFilter.value) params.append('deviceType', deviceFilter.value)
      if (statusFilter.value && statusFilter.value.length > 0) {
        statusFilter.value.forEach(s => params.append('status', s))
      }
      
      if (params.toString()) url += `?${params.toString()}`

      const res = await fetch(url)
      const json = await res.json()
      pipeList.value = json?.data?.items || json?.items || []
    } catch { pipeList.value = [] }
    finally { pipeLoading.value = false }
}

function resetFilters() {
  keyword.value = ''
  modelFilter.value = ''
  deviceFilter.value = ''
  statusFilter.value = []
  loadPipelines()
}

function setStatusFilter(statuses: TaskStatus[]) {
  statusFilter.value = statuses
  loadPipelines()
}

onMounted(async () => { await loadPipelines() })

// Actions
function onDeletePipeline(record: any) {
    const id = record.id
    const name = record.taskName || record.modelName
    try {
      pipeList.value = pipeList.value.filter(p => p.id !== id)
      fetch(`/api/surrogate/pipelines/${id}`, { method: 'DELETE' }).then(() => {
          message.success(`已删除构建任务：${name}`)
          loadSummary()
      })
    } catch {}
}

function onStartPipeline(record: any) {
     fetch(`/api/surrogate/pipelines/${record.id}/start`, { method: 'POST' }).then(res => res.json()).then(json => {
         if(json.code === 0) {
             message.success('任务已启动')
             loadPipelines()
             loadSummary()
         } else {
             message.error(json.message || '启动失败')
         }
     })
}

function onStopTask(id: string | number) {
  message.info('中止暂未实现: ' + String(id))
}

// Status Drawer Logic
// drawerOpen and selectedTask moved to top
// const drawerOpen = ref(false)
// const selectedTask = ref<any>(null)

function onViewStatus(record: any) {
    selectedTask.value = record
    drawerOpen.value = true
}

function statusTag(status: string) {
  const map: Record<string, { color: string; text: string }> = {
    pending: { color: 'default', text: '未运行' },
    running: { color: 'processing', text: '运行中' },
    succeeded: { color: 'success', text: '成功' },
    failed: { color: 'error', text: '失败' },
  }
  return map[status] || map.pending
}

// Render Cell
function renderNodeCell(record: any) {
    const status = record.status || 'pending'
    const st = statusTag(status)
    const created = record.createdAt ? dayjs(record.createdAt).format('YYYY-MM-DD HH:mm') : '—'
    const creator = record.creator || record.createdBy || '未知'
    const showModel = true // Always show model for now
    
    const runBtn = h(Button, { size: 'small', type: 'primary', disabled: status === 'running' || status === 'succeeded', onClick: () => onStartPipeline(record) }, () => '执行')
    const stopBtn = h(Button, { size: 'small', danger: true, disabled: status !== 'running', onClick: () => onStopTask(record.id) }, () => '中止')
    const viewBtn = h(Button, { size: 'small', type: 'primary', ghost: true, onClick: () => onViewStatus(record) }, () => '查看状态')
    const delBtn = h(Popconfirm, { title: '确认删除该任务？', okText: '删除', cancelText: '取消', onConfirm: () => onDeletePipeline(record) }, {
        default: () => h(Button, { size: 'small', danger: true }, () => '删除')
    })
    
    return h('div', { class: 'py-2 flex justify-between items-center' }, [
        h('div', { class: 'flex flex-col gap-1' }, [
            h('div', { style: 'font-weight:600;font-size:16px;color:#0f172a;' }, record.taskName || record.name),
            h('div', { style: 'display:flex;gap:10px;align-items:center;color:#64748b;font-size:13px;' }, [
                showModel ? h('span', {}, `模型: ${record.modelName}`) : null,
                record.deviceType ? h(Tag, { color: 'geekblue' }, { default: () => `设备: ${record.deviceType}` }) : null,
                h(Tag, { color: st.color }, { default: () => st.text }),
                h('span', {}, `创建: ${created}`),
                h('span', {}, `创建人: ${creator}`),
            ])
        ]),
        h('div', { style: 'display:flex;gap:8px;' }, [ runBtn, stopBtn, viewBtn, delBtn ])
    ])
}

const columns = [
    { title: '任务列表', key: 'node', customRender: ({ record }: any) => renderNodeCell(record) }
]

const statusOptions = [
    { label: '未运行', value: 'pending' },
    { label: '运行中', value: 'running' },
    { label: '成功', value: 'succeeded' },
    { label: '失败', value: 'failed' },
]
</script>

<template>
  <div class="p-5">
    <Card>
      <div class="summary-header">代理模型构建任务信息总览</div>
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
          <Input v-model:value="keyword" placeholder="搜索任务名称" allow-clear style="width:220px" @pressEnter="loadPipelines" />
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
          <Button type="primary" shape="round" @click="loadPipelines">搜索</Button>
          <Button @click="resetFilters">重置</Button>
          <Divider type="vertical" />
          <Button type="default" @click="onCreate">新增</Button>
        </Space>
      </div>
      <Table
        :data-source="pipeList"
        :loading="pipeLoading"
        :rowKey="(r:any)=>r.id"
        :pagination="{ pageSize: 8 }"
        :columns="columns"
      />
    </Card>

    <SurrogateStatusDrawer 
      v-model:open="drawerOpen" 
      :task-id="selectedTask?.id || null" 
      :task-data="selectedTask" 
    />
    
    <StartSurrogateModal ref="startModalRef" @success="handleTaskCreated" />
  </div>
</template>

<style scoped>
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.transition-shadow { transition: box-shadow 0.3s; }
.cursor-pointer { cursor: pointer; }
.hover\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
.mb-5 { margin-bottom: 20px; }
</style>