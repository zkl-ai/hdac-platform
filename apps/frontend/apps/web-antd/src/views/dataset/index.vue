<script setup lang="ts">
import { ref, onMounted, reactive, computed, watch } from 'vue'
import { Card, Table, Button, Modal, Form, Input, Select, message, Popconfirm, Tag, Row, Col, Statistic, Tooltip } from 'ant-design-vue'
import { DatabaseOutlined, SearchOutlined, FolderOpenOutlined, HddOutlined, PlusOutlined, DeleteOutlined, PieChartOutlined } from '@ant-design/icons-vue'

const loading = ref(false)
const items = ref<any[]>([])
const models = ref<any[]>([])
const totalSize = ref('0 B')
const modalVisible = ref(false)
const modalLoading = ref(false)
const keywordInput = ref('')
const keyword = ref('')

const totalDatasets = computed(() => items.value.length)
const coveredTypes = computed(() => new Set(items.value.map(i => i.type)).size)
const linkedModels = computed(() => {
  const modelNames = new Set<string>()
  for (const m of models.value) {
      for (const dev of (m.children || [])) {
          for (const v of (dev.children || [])) {
              if (v.dataset && items.value.some(d => d.name === v.dataset)) {
                  modelNames.add(m.name)
              }
          }
      }
  }
  return modelNames.size
})
const totalReferences = computed(() => {
  let count = 0
  for (const m of models.value) {
      for (const dev of (m.children || [])) {
          for (const v of (dev.children || [])) {
              if (v.dataset && items.value.some(d => d.name === v.dataset)) {
                  count++
              }
          }
      }
  }
  return count
})

const filteredItems = computed(() => {
  if (!keyword.value) return items.value
  const k = keyword.value.trim().toLowerCase()
  return items.value.filter(item => 
    item.name.toLowerCase().includes(k) || 
    item.type.toLowerCase().includes(k) || 
    (item.description && item.description.toLowerCase().includes(k))
  )
})

let kwTimer: any = null
watch(keywordInput, (val) => {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => { keyword.value = String(val || '').trim().toLowerCase() }, 250)
})

const columns = [
  { title: '名称', dataIndex: 'name', width: 150 },
  { title: '创建人', dataIndex: 'createdBy', width: 100 },
  { title: '路径', dataIndex: 'path' },
  { title: '类型', dataIndex: 'type', width: 150 },
  { title: '占用空间', dataIndex: 'size', width: 120 },
  { title: '描述', dataIndex: 'description' },
  { title: '创建时间', dataIndex: 'createdAt', width: 180 },
  { title: '操作', key: 'action', width: 100 }
]

const formState = reactive({
  name: '',
  path: '',
  type: 'Image Classification',
  description: ''
})

const fetchDatasets = async () => {
  loading.value = true
  try {
    const res = await fetch('/api/datasets')
    const json = await res.json()
    items.value = json.data?.items || []
    totalSize.value = json.data?.totalSize || '0 B'
  } catch (e) {
    message.error('加载数据集失败')
  } finally {
    loading.value = false
  }
}

const fetchModels = async () => {
  try {
    const res = await fetch('/api/models/tree')
    const json = await res.json()
    models.value = json.data?.items || []
  } catch (e) {
    console.error(e)
  }
}

const handleCreate = () => {
  formState.name = ''
  formState.path = ''
  formState.type = 'Image Classification'
  formState.description = ''
  modalVisible.value = true
}

const handleSubmit = async () => {
  if (!formState.name || !formState.path) {
    message.error('名称和路径为必填项')
    return
  }
  
  modalLoading.value = true
  try {
    const res = await fetch('/api/datasets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(formState)
    })
    const json = await res.json()
    if (json.code === 0) {
      message.success('创建成功')
      modalVisible.value = false
      fetchDatasets()
    } else {
      message.error(json.message || '创建失败')
    }
  } catch (e) {
    message.error('创建失败')
  } finally {
    modalLoading.value = false
  }
}

const handleDelete = async (id: number) => {
  try {
    const res = await fetch(`/api/datasets/${id}`, { method: 'DELETE' })
    const json = await res.json()
    if (json.code === 0) {
      message.success('删除成功')
      fetchDatasets()
    } else {
      message.error(json.message || '删除失败')
    }
  } catch (e) {
    message.error('删除失败')
  }
}

const resetFilters = () => {
  keywordInput.value = ''
  keyword.value = ''
}

onMounted(() => {
  fetchDatasets()
  fetchModels()
})
</script>

<template>
  <div class="dataset-page p-5">
    <Card class="summary">
      <div class="summary-header">数据集概览</div>
      <Row :gutter="16">
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-blue-50">
            <Statistic title="数据集总数" :value="totalDatasets" :value-style="{ color: '#1d4ed8' }">
              <template #prefix><DatabaseOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-sky-50">
            <Statistic title="覆盖任务类型" :value="coveredTypes" :value-style="{ color: '#0ea5e9' }">
              <template #prefix><FolderOpenOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="24" :sm="8" :md="8" :lg="8">
          <Card :bordered="false" class="stat-box bg-purple-50">
            <Statistic title="总占用空间" :value="totalSize" :value-style="{ color: '#7e22ce' }">
              <template #prefix><PieChartOutlined /></template>
            </Statistic>
          </Card>
        </Col>
      </Row>
    </Card>

    <Card class="table-card">
      <div class="toolbar-row">
        <div class="toolbar-left">
          <Tooltip title="按名称、类型或描述过滤">
            <Input
              v-model:value="keywordInput"
              placeholder="搜索数据集"
              allow-clear
              style="width: 300px"
              @pressEnter="keyword = String(keywordInput || '').trim().toLowerCase()"
            />
          </Tooltip>
          
          <Tooltip title="应用当前关键字搜索">
            <Button type="default" @click="keyword = String(keywordInput || '').trim().toLowerCase()">
              <template #icon><SearchOutlined /></template>
              搜索
            </Button>
          </Tooltip>
          <Button type="default" @click="resetFilters">
            重置
          </Button>
        </div>
        <div class="toolbar-right">
          <Button type="primary" @click="handleCreate">
            <template #icon><PlusOutlined /></template>
            新增
          </Button>
        </div>
      </div>
      
      <Table
        :columns="columns"
        :data-source="filteredItems"
        :loading="loading"
        :pagination="{ pageSize: 10 }"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'action'">
            <Popconfirm title="确定删除该数据集吗？" @confirm="handleDelete(record.id)">
              <Button type="link" danger size="small">
                <template #icon><DeleteOutlined /></template>
                删除
              </Button>
            </Popconfirm>
          </template>
          <template v-if="column.dataIndex === 'type'">
             <Tag color="blue">{{ record.type }}</Tag>
          </template>
        </template>
      </Table>
    </Card>

    <Modal
      v-model:open="modalVisible"
      title="新增数据集"
      @ok="handleSubmit"
      :confirmLoading="modalLoading"
    >
      <Form layout="vertical">
        <Form.Item label="名称" required>
          <Input v-model:value="formState.name" placeholder="例如：CIFAR-10" />
        </Form.Item>
        <Form.Item label="服务器路径" required tooltip="数据集在服务器上的绝对路径">
          <Input v-model:value="formState.path" placeholder="例如：/data/workspace/datasets/cifar-10" />
        </Form.Item>
        <Form.Item label="类型">
          <Select v-model:value="formState.type">
            <Select.Option value="Image Classification">图像分类</Select.Option>
            <Select.Option value="Object Detection">目标检测</Select.Option>
            <Select.Option value="Segmentation">语义分割</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item label="描述">
          <Input.TextArea v-model:value="formState.description" />
        </Form.Item>
      </Form>
    </Modal>
  </div>
</template>

<style scoped>
.dataset-page { display: grid; gap: 8px; }
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.toolbar-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; }
.table-card { padding-top: 8px; }
.stat-box { border-radius: 8px; }
.bg-blue-50 { background-color: #eff6ff; }
.bg-sky-50 { background-color: #f0f9ff; }
.bg-purple-50 { background-color: #faf5ff; }
.bg-green-50 { background-color: #f0fdf4; }
</style>
