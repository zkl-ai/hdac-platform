<script setup lang="ts">
import { ref, computed } from 'vue'
import { Card, Space, Input, Select, Button, Table, Modal, Form, FormItem, message, Steps, Popconfirm, Row, Col, Statistic } from 'ant-design-vue'
import { h } from 'vue'
import axios from 'axios'
import { DatabaseOutlined, CheckCircleOutlined, CloseCircleOutlined, CloudServerOutlined, CodeOutlined } from '@ant-design/icons-vue'
import TerminalModal from './components/TerminalModal.vue'

import 'ant-design-vue/es/card/style'
import 'ant-design-vue/es/row/style'
import 'ant-design-vue/es/col/style'
import 'ant-design-vue/es/statistic/style'
import 'ant-design-vue/es/space/style'
import 'ant-design-vue/es/input/style'
import 'ant-design-vue/es/select/style'
import 'ant-design-vue/es/button/style'
import 'ant-design-vue/es/table/style'
import 'ant-design-vue/es/modal/style'
import 'ant-design-vue/es/form/style'
import 'ant-design-vue/es/input/style'
import 'ant-design-vue/es/popconfirm/style'

type Status = 'online' | 'offline'
interface DeviceRow {
  id: number
  type: string
  ip: string
  temperature: number
  memUsage: number
  cpuUsage: number
  gpuUsage: number
  status: Status
  regStatus?: 'online' | 'offline'
  os: string
}

const keyword = ref('')
const typeFilter = ref<string | undefined>()
const statusFilter = ref<Status | undefined>()
const regFilter = ref<'offline' | undefined>()

const raw = ref<DeviceRow[]>([])

const totalDevices = computed(() => raw.value.length)
const onlineCount = computed(() => raw.value.filter(d => d.status === 'online').length)
const offlineCount = computed(() => raw.value.filter(d => d.status === 'offline').length)
const registeredCount = computed(() => raw.value.filter(d => d.regStatus !== 'offline').length)

function setStatusFilter(status: Status | undefined) {
  statusFilter.value = status
}

const devices = computed(() => {
  return raw.value.filter((d) =>
    (!typeFilter.value || d.type === typeFilter.value) &&
    (!statusFilter.value || d.status === statusFilter.value) &&
    (!regFilter.value || d.regStatus === regFilter.value) &&
    (!keyword.value || d.type.toLowerCase().includes(keyword.value.toLowerCase()) || d.ip.includes(keyword.value))
  )
})

async function loadFromProm() {
  try {
    const { data } = await axios.get('/api/devices/metrics')
    const items = data?.data?.items || data?.items || []
    raw.value = items.map((it: any, idx: number) => ({ id: idx + 1, type: it.type, ip: it.ip, temperature: it.temperature, memUsage: it.memUsage, cpuUsage: it.cpuUsage, gpuUsage: it.gpuUsage, status: it.status as Status, regStatus: it.regStatus, os: it.os }))
  } catch (e) {
    // 保留原空数据并提示
    message.warning('无法从 Prometheus 加载设备数据')
  }
}

loadFromProm()

const columns = [
  { title: '设备类型', dataIndex: 'type', key: 'type' },
  { title: 'IP', dataIndex: 'ip', key: 'ip' },
  { title: '温度(°C)', dataIndex: 'temperature', key: 'temperature', customRender: ({text}: any) => (text === null || text === undefined ? '—' : `${text}`) },
  { title: '内存占用(%)', dataIndex: 'memUsage', key: 'memUsage', customRender: ({text}: any) => (text === null || text === undefined ? '—' : `${Number(text).toFixed(2)}%`) },
  { title: 'CPU 利用率(%)', dataIndex: 'cpuUsage', key: 'cpuUsage', customRender: ({text}: any) => (text === null || text === undefined ? '—' : `${Number(text).toFixed(2)}%`) },
  { title: 'GPU 利用率(%)', dataIndex: 'gpuUsage', key: 'gpuUsage', customRender: ({text}: any) => (text === null || text === undefined ? '—' : `${Number(text).toFixed(2)}%`) },
  { title: '运行状态', dataIndex: 'status', key: 'status',
    customRender: ({ record }: any) => {
      const text = record.status
      const tag = record.regStatus === 'offline' ? '（已下线）' : ''
      return text === 'online' ? `在线${tag}` : `离线${tag}`
    } },
  { title: '系统信息', dataIndex: 'os', key: 'os' },
  { title: '操作', key: 'action',
    customRender: ({ record }: any) => {
      return h(
        Space,
        null,
        {
          default: () => [
            h(
              Button,
              { type: 'link', onClick: () => handleLogin(record), disabled: record.status !== 'online' },
              { default: () => [h(CodeOutlined), ' 登录'] }
            ),
            h(
              Popconfirm,
              { title: '确认上线并加入采集？', onConfirm: () => handleOnline(record), disabled: record.status === 'online' },
              {
                default: () => h(Button, { type: 'link', disabled: record.status === 'online' }, { default: () => '上线' }),
              },
            ),
            h(
              Popconfirm,
              { title: '确认下线并清理采集？', onConfirm: () => handleOffline(record), disabled: record.status !== 'online' },
              {
                default: () => h(Button, { type: 'link', danger: true, disabled: record.status !== 'online' }, { default: () => '下线' }),
              },
            ),
            h(
              Popconfirm,
              { title: '确认从采集中移除？', onConfirm: () => handleRemove(record) },
              {
                default: () => h(Button, { type: 'link', danger: record.status === 'online' }, { default: () => '移除' }),
              },
            ),
          ],
        },
      )
    }
  },
]

const typeOptions = [ 'Jetson Nano', 'Jetson Xavier NX', 'Raspberry Pi 4B' ].map(v=>({label:v,value:v}))
const statusOptions = [
  {label:'在线',value:'online'},
  {label:'离线',value:'offline'},
]
const regStatusOptions = [
  {label:'已下线（可上线）', value:'offline'},
]

const showModal = ref(false)
const showTerminal = ref(false)
const currentDeviceIp = ref('')
const form = ref({ type: undefined as string | undefined, ip: '', username: '', password: '', port: 22 })
const saving = ref(false)
const step = ref(0)
const cancelled = ref(false)
const lastStatus = ref<Record<string, any>>({})

const resetForm = () => { form.value = { type: undefined, ip: '', username: '', password: '', port: 22 } }
const openModal = () => { resetForm(); cancelled.value = false; step.value = 0; showModal.value = true }
const submitForm = async () => {
  if (!form.value.type || !form.value.ip || !form.value.username || !form.value.password) return
  try {
    saving.value = true
    cancelled.value = false
    // 先登记设备凭据（离线），随后上线
    await axios.post('/api/devices/register', { ip: form.value.ip, username: form.value.username, password: form.value.password, deviceType: form.value.type, port: Number(form.value.port) || 22 })
    await axios.post('/api/devices/online', { ip: form.value.ip, username: form.value.username, password: form.value.password, deviceType: form.value.type, port: Number(form.value.port) || 22 })
    message.success('设备引导安装已启动')
    step.value = 1
    // 轮询 Prometheus 状态
    const maxTries = 60
    for (let i = 0; i < maxTries; i++) {
      if (cancelled.value) break
      const { data } = await axios.get('/api/devices/status', { params: { ip: form.value.ip } })
      const s = data?.data || data
      lastStatus.value = s || {}
      if (s?.inTargets) step.value = Math.max(step.value, 2)
      if ((s?.nodeExporterAlive && s?.tegrastatsAlive) || (s?.nodeExporterUp && s?.tegrastatsUp)) { step.value = 3; break }
      await new Promise(r => setTimeout(r, 3000))
    }
    if (cancelled.value) { message.warning('安装进度已终止') }
    else if (step.value === 3) { message.success('Prometheus 目标已就绪') } else { message.warning('Prometheus 目标尚未完全就绪，请稍后刷新查看') }
    await loadFromProm()
    showModal.value = false
  } catch (e) {
    message.error('设备引导安装失败')
  } finally { saving.value = false }
}

const abortInstall = async () => {
  cancelled.value = true
  saving.value = false
  try {
    await axios.post('/api/devices/offline', { ip: form.value.ip, username: form.value.username, password: form.value.password, port: Number(form.value.port) || 22 })
    message.success('已终止并清理设备采集（下线）')
  } catch (e) {
    message.warning('终止请求发送失败，但轮询已停止')
  }
}

async function handleOffline(record: any) {
  try {
    await axios.post('/api/devices/offline', { ip: record.ip, username: form.value.username, password: form.value.password, port: Number(form.value.port) || 22 })
    message.success('设备已下线（停止服务并从采集中移除，但保留登记）')
    await loadFromProm()
  } catch (e) {
    message.error('下线失败')
  }
}

async function handleRemove(record: any) {
  try {
    await axios.post('/api/devices/remove', { ip: record.ip })
    message.success('已移除设备目标')
    await loadFromProm()
  } catch (e) {
    message.error('移除失败')
  }
}


async function handleOnline(record: any) {
  try {
    if (!form.value.username || !form.value.password) {
      form.value.type = record.type
      form.value.ip = record.ip
      form.value.port = Number(form.value.port) || 22
      showModal.value = true
      message.info('请填写用户名和密码以执行上线')
      return
    }
    await axios.post('/api/devices/online', { ip: record.ip, username: form.value.username, password: form.value.password, deviceType: record.type, port: Number(form.value.port) || 22 })
    message.success('设备已上线并加入采集')
    await loadFromProm()
  } catch (e) {
    message.error('上线失败')
  }
}

function handleLogin(record: any) {
  currentDeviceIp.value = record.ip
  showTerminal.value = true
}
</script>

<template>
  <div class="p-5">
    <Card style="margin-bottom:12px">
      <div class="summary-header">设备总览</div>
      <Row :gutter="16">
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-blue-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter(undefined)">
            <Statistic title="全部设备" :value="totalDevices" :value-style="{ color: '#1d4ed8' }">
              <template #prefix><CloudServerOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-green-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter('online')">
            <Statistic title="在线" :value="onlineCount" :value-style="{ color: '#15803d' }">
              <template #prefix><CheckCircleOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-red-50 cursor-pointer hover:shadow-md transition-shadow" @click="setStatusFilter('offline')">
            <Statistic title="离线" :value="offlineCount" :value-style="{ color: '#b91c1c' }">
              <template #prefix><CloseCircleOutlined /></template>
            </Statistic>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card style="margin-top:12px">
      <Space wrap>
        <Input v-model:value="keyword" placeholder="搜索设备/IP" allow-clear style="width:220px" />
        <Select v-model:value="typeFilter" placeholder="设备类型" allow-clear style="width:180px" :options="typeOptions" />
        <Select v-model:value="statusFilter" placeholder="运行状态" allow-clear style="width:160px" :options="statusOptions" />
        <Button type="primary" shape="round" @click="openModal">新增</Button>
      </Space>
    </Card>

    <Card style="margin-top:12px">
      <Table :columns="columns" :data-source="devices" row-key="id" size="small" />
    </Card>

    <Modal v-model:open="showModal" title="新增设备" :mask-closable="false" :destroy-on-close="true">
      <Steps :current="step" size="small" style="margin-bottom:10px">
        <Steps.Step title="安装中" />
        <Steps.Step title="加入Targets" />
        <Steps.Step title="目标UP" />
      </Steps>
      <div class="status-box">
        <div class="status-item">
          <span class="label">Prometheus可达</span>
          <span :class="(lastStatus.promReachable ? 'ok' : 'bad')">{{ lastStatus.promReachable ? '是' : '否' }}</span>
        </div>
        <div class="status-item">
          <span class="label">已加入Targets</span>
          <span :class="(lastStatus.inTargets ? 'ok' : 'bad')">{{ lastStatus.inTargets ? '是' : '否' }}</span>
        </div>
        <div class="status-item">
          <span class="label">9100 Alive</span>
          <span :class="(lastStatus.nodeExporterAlive ? 'ok' : 'bad')">{{ lastStatus.nodeExporterAlive ? '是' : '否' }}</span>
        </div>
        <div class="status-item">
          <span class="label">9200 Alive</span>
          <span :class="(lastStatus.tegrastatsAlive ? 'ok' : 'bad')">{{ lastStatus.tegrastatsAlive ? '是' : '否' }}</span>
        </div>
        <div class="status-item">
          <span class="label">9100 Up</span>
          <span :class="(lastStatus.nodeExporterUp ? 'ok' : 'warn')">{{ lastStatus.nodeExporterUp ? '1' : '0' }}</span>
        </div>
        <div class="status-item">
          <span class="label">9200 Up</span>
          <span :class="(lastStatus.tegrastatsUp ? 'ok' : 'warn')">{{ lastStatus.tegrastatsUp ? '1' : '0' }}</span>
        </div>
      </div>
      <Form layout="vertical">
        <FormItem label="设备类型" :required="true">
          <Select v-model:value="form.type" :options="typeOptions" placeholder="请选择" :disabled="saving" />
        </FormItem>
        <FormItem label="IP" :required="true">
          <Input v-model:value="form.ip" placeholder="例如 10.0.0.11" :disabled="saving" />
        </FormItem>
        <FormItem label="用户名" :required="true">
          <Input v-model:value="form.username" placeholder="例如 ubuntu" :disabled="saving" />
        </FormItem>
        <FormItem label="密码" :required="true">
          <Input v-model:value="form.password" type="password" placeholder="请输入密码" :disabled="saving" />
        </FormItem>
        <FormItem label="SSH端口">
          <Input v-model:value="form.port" type="number" placeholder="默认 22" :disabled="saving" />
        </FormItem>
      </Form>
      <template #footer>
        <Space>
          <Button v-if="!saving" @click="showModal=false">取消</Button>
          <Button v-if="!saving" type="primary" @click="submitForm">保存</Button>
          <Button v-else danger @click="abortInstall">终止进度</Button>
        </Space>
      </template>
    </Modal>
    <TerminalModal v-model:open="showTerminal" :ip="currentDeviceIp" />
  </div>
  
</template>

<style scoped>
.p-5 { padding: 20px; }
.status-box { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-bottom: 8px; }
.status-item { display:flex; justify-content: space-between; padding:6px 10px; border:1px solid #e5e7eb; border-radius:8px; background:#fafafa; font-size:12px; }
.status-item .label { color:#64748b; }
.status-item .ok { color:#16a34a; font-weight:600; }
.status-item .bad { color:#dc2626; font-weight:600; }
.status-item .warn { color:#d97706; font-weight:600; }
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.transition-shadow { transition: box-shadow 0.3s; }
.cursor-pointer { cursor: pointer; }
.hover\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
.stat-box { border-radius: 8px; }
.bg-blue-50 { background-color: #eff6ff; }
.bg-green-50 { background-color: #f0fdf4; }
.bg-red-50 { background-color: #fef2f2; }
.bg-indigo-50 { background-color: #eef2ff; }
</style>
