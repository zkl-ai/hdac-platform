<script setup lang="ts">
import { ref, onMounted, onActivated, computed, h, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Card, Row, Col, Input, Select, Button, Table, Tag, Popconfirm, message, Statistic, Divider, Space } from 'ant-design-vue'
import { FolderOpenOutlined, SyncOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons-vue'
import GrayTaskStatusDrawer from './GrayTaskStatusDrawer.vue'
import StartGrayDeployModal from './StartGrayDeployModal.vue'

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

const route = useRoute()
const router = useRouter()
const keyword = ref('')
const modelFilter = ref(undefined)
const deviceFilter = ref(undefined)
const statusFilter = ref<TaskStatus[]>([])
const modelOptions = ref<string[]>([])
const deviceOptions = ref<string[]>([])

const summary = ref({
  total: 0,
  prepareTotal: 0,
  weightTotal: 0,
  prepareRunning: 0,
  weightRunning: 0,
  fullTotal: 0,
  fullRunning: 0,
  running: 0,
  pending: 0,
  succeeded: 0,
  failed: 0
})

async function loadSummary() {
  try {
    const res = await fetch('/api/deploy/tasks/summary')
    const json = await res.json()
    const data = json?.data || json
    if (data) {
       summary.value = { ...summary.value, ...data }
       if (data.running === undefined) {
          summary.value.running = (data.prepareRunning || 0) + (data.weightRunning || 0) + (data.fullRunning || 0)
       }
    }
  } catch {}
}

async function loadModels() {
  try {
    const res = await fetch('/api/models/tree')
    const json = await res.json()
    const items = json?.data?.items || json?.items || []
    
    // Filter for search options (only showing names)
    const names = items.map((m: any) => m.name).filter(Boolean)
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

const createModalRef = ref()

function onCreate() {
  createModalRef.value?.show()
}

const rawTasks = ref<any[]>([])
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
    
    const url = qs.length ? `/api/deploy/tasks?${qs.join('&')}` : '/api/deploy/tasks'
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
    selectedTaskData.value = record
    statusDrawerOpen.value = true
}

function renderNodeCell(record: any) {
  const showModel = String(record.name || '') !== String(record.modelName || '')
  const created = record.createdAt || ''
  const creator = record.creator || ''
  const st = statusTag(record.status || 'pending')
  
  const runBtn = h(Button, { 
    size: 'small', 
    type: 'primary', 
    loading: actionLoading.value[record.id],
    disabled: record.status === 'running' || record.status === 'succeeded',
    onClick: () => onRunTask(record.id) 
  }, () => '执行')

  const stopBtn = h(Button, { 
    size: 'small', 
    danger: true, 
    loading: actionLoading.value[record.id],
    disabled: record.status !== 'running',
    onClick: () => onStopTask(record.id) 
  }, () => '中止')

  const viewBtn = h(Button, { size: 'small', type: 'primary', ghost: true, onClick: () => onViewStatus(record) }, () => '查看状态')
  const delBtn = h(Popconfirm, { title: '确认删除该任务？', okText: '删除', cancelText: '取消', onConfirm: () => onDeleteTask(record) }, {
    default: () => h(Button, { size: 'small', danger: true, disabled: record.status === 'running' }, () => '删除')
  })
  
  return h('div', { class: 'py-2 flex justify-between items-center' }, [
    h('div', { class: 'flex flex-col gap-1' }, [
      h('div', { style: 'font-weight:600;font-size:16px;color:#0f172a;' }, record.name),
      h('div', { style: 'display:flex;gap:10px;align-items:center;color:#64748b;font-size:13px;' }, [
        showModel ? h('span', {}, `模型: ${record.modelName || record.candidateModel}`) : null,
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

const columns = [
  { title: '任务列表', key: 'node', customRender: ({ record }: any) => renderNodeCell(record) },
]

function resetFilters() {
  keyword.value = ''
  modelFilter.value = undefined
  deviceFilter.value = undefined
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
    nextTick(() => {
        onCreate()
    })
  } else if (action === 'execute') {
    statusFilter.value = ['pending']
  } else if (action === 'view') {
    // Default view
  }

  // Cleanup
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
  checkAction() // Check action immediately
  
  await loadSummary()
  loadModels()
  loadDevices()
  await loadTasks()
})

onActivated(() => {
    checkAction()
})

const actionLoading = ref<Record<string, boolean>>({})

async function onStopTask(id: string | number) {
  try {
    actionLoading.value[id] = true
    const res = await fetch(`/api/deploy/tasks/${id}/stop`, { method: 'POST' })
    const json = await res.json()
    if (json.code === 0) {
      message.success('任务已中止')
      await loadTasks()
      loadSummary()
    } else {
      message.error(json.message || '中止失败')
    }
  } catch {
    message.error('中止请求失败')
  } finally {
    actionLoading.value[id] = false
  }
}

async function onRunTask(id: string | number) {
  try {
    actionLoading.value[id] = true
    const res = await fetch(`/api/deploy/tasks/${id}/start`, { method: 'POST' })
    const json = await res.json()
    if (json.code === 0) {
      message.success('任务已开始执行')
      await loadTasks()
      loadSummary()
    } else {
      message.error(json.message || '启动失败')
    }
  } catch {
    message.error('启动请求失败')
  } finally {
    actionLoading.value[id] = false
  }
}

async function onDeleteTask(record: any) {
  try {
    const id = record?.id
    const name = String(record?.name || record?.modelName || '任务')
    
    const res = await fetch(`/api/deploy/tasks/${id}`, { method: 'DELETE' })
    const json = await res.json()
    
    if (json.code === 0) {
        message.success('已删除任务：' + name)
        await loadTasks()
        loadSummary()
    } else {
        message.error(json.message || '删除失败')
    }
  } catch {
      message.error('删除请求失败')
  }
}

</script>

<template>
  <div class="p-5 gray-page">
    <Card>
      <div class="summary-header">DNN模型部署任务信息总揽</div>
      <Row :gutter="16">
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-blue-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter([])">
            <Statistic title="全部任务" :value="summary.total" :value-style="{ color: '#1d4ed8' }">
              <template #prefix><FolderOpenOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-indigo-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(['running'])">
            <Statistic title="运行中" :value="summary.running" :value-style="{ color: '#4338ca' }">
              <template #prefix><SyncOutlined spin /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-green-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(['pending'])">
            <Statistic title="排队中" :value="summary.pending" :value-style="{ color: '#15803d' }">
              <template #prefix><CheckCircleOutlined /></template>
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
      <!-- Search Area merged into the same card -->
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
        :data-source="rawTasks"
        :loading="loading"
        :rowKey="(r:any)=>r.id"
        :pagination="{ pageSize: 8 }"
        :columns="columns"
      />
    </Card>

    <GrayTaskStatusDrawer 
      v-model:open="statusDrawerOpen" 
      :task-id="selectedTaskId" 
      :task-data="selectedTaskData"
      @close="statusDrawerOpen = false"
    />
    
    <StartGrayDeployModal ref="createModalRef" @success="loadTasks" />
  </div>
</template>

<style scoped>
.gray-page { display: grid; gap: 8px; }
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.transition-shadow { transition: box-shadow 0.3s; }
.cursor-pointer { cursor: pointer; }
.hover\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
.mb-5 { margin-bottom: 20px; }
.mb-4 { margin-bottom: 16px; }
</style>
