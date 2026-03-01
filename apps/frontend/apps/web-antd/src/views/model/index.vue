<script setup lang="ts">
import { ref, computed, onMounted, h, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Card, Row, Col, Input, Select, Button, Table, Tag, Tooltip, Modal, Form, InputNumber, Switch, message, Statistic } from 'ant-design-vue'
import { AppstoreOutlined, CodeSandboxOutlined, PlusOutlined, SearchOutlined, DeploymentUnitOutlined, FileZipOutlined } from '@ant-design/icons-vue'
import StartCompressModal from '../compress-task/StartCompressModal.vue'

import 'ant-design-vue/es/card/style'
import 'ant-design-vue/es/row/style'
import 'ant-design-vue/es/col/style'
import 'ant-design-vue/es/input/style'
import 'ant-design-vue/es/select/style'
import 'ant-design-vue/es/button/style'
import 'ant-design-vue/es/table/style'
import 'ant-design-vue/es/tag/style'
import 'ant-design-vue/es/tooltip/style'
import 'ant-design-vue/es/modal/style'
import 'ant-design-vue/es/form/style'
import 'ant-design-vue/es/input-number/style'
import 'ant-design-vue/es/switch/style'
import 'ant-design-vue/es/statistic/style'

type ModelType = 'DNN' | 'Surrogate'
const keywordInput = ref('')
const keyword = ref('')
const typeFilter = ref<ModelType | ''>('')
const datasetFilter = ref<string | ''>('')
const deviceFilter = ref<string | ''>('')
const categoryFilter = ref<string | ''>('')
const sortSelect = ref<string | ''>('')
const tree = ref<any[]>([])
const compressModalRef = ref()
const router = useRouter()

const totalModels = computed(() => tree.value.length)
const dnnTotal = computed(() => tree.value.filter((m: any) => m.type === 'DNN').length)
const surrogateTotal = computed(() => {
  // Recursively count Level 3 items that are Proxy Models
  const countNodes = (nodes: any[]): number => {
    let c = 0
    for (const node of nodes) {
      if (node.level === 3 && (node.type === 'Surrogate' || node.name.startsWith('Surrogate-'))) {
        c++
      }
      if (node.children && node.children.length > 0) {
        c += countNodes(node.children)
      }
    }
    return c
  }
  return countNodes(tree.value || [])
})
const compressedCount = computed(() => {
  try {
    let count = 0
    for (const m of (tree.value || [])) {
      for (const dev of (m.children || [])) {
        for (const leaf of (dev.children || [])) {
          if (leaf && leaf.compressed === true) count++
        }
      }
    }
    return count
  } catch { return 0 }
})
// 移除设备类型数与模型类别数统计，按需求不展示

const deviceOptions = computed<string[]>(() => {
  try {
    const types: string[] = []
    for (const m of (tree.value || [])) {
      for (const dev of (m.children || [])) {
         if (dev.deviceType) types.push(dev.deviceType)
      }
    }
    return Array.from(new Set(types))
  } catch { return [] }
})

// datasetOptions removed as requested to simplify

const categoryOptions = computed<string[]>(() => ['原始模型', '压缩模型'])
const taskTypeMap: Record<string, string> = {
  ResNet50: '图片分类',
  VGG19: '图片分类',
  MobileNetV1: '图片分类',
  YOLOv8n: '目标检测',
}

async function loadModels() {
  try {
    const t = typeFilter.value
    const url = t ? `/api/models/tree?type=${encodeURIComponent(t)}` : '/api/models/tree'
    const res = await fetch(url)
    const json = await res.json()
    const items = json?.data?.items || json?.items || []

    // Assign levels recursively if not present (backend provides it now, but safe to keep)
    const assignLevels = (nodes: any[], level: number) => {
        nodes.forEach(node => {
            if (!node.level) node.level = level
            if (node.children) assignLevels(node.children, level + 1)
        })
    }
    assignLevels(items, 1)

    tree.value = items
  } catch (e) {
    message.error('加载模型库数据失败')
  }
}

onMounted(loadModels)
watch(typeFilter, loadModels)
let kwTimer: any = null
watch(keywordInput, (val) => {
  if (kwTimer) clearTimeout(kwTimer)
  kwTimer = setTimeout(() => { keyword.value = String(val || '').trim().toLowerCase() }, 250)
})
// Removed datasetFilter watcher

function levenshtein(a: string, b: string) {
  const m = a.length, n = b.length
  if (m === 0) return n
  if (n === 0) return m
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array<number>(n + 1).fill(0))
  const firstRow = dp[0] as number[]
  for (let j = 0; j <= n; j++) firstRow[j] = j
  for (let i = 1; i <= m; i++) {
    const row = dp[i] as number[]
    const prevRow = dp[i - 1] as number[]
    row[0] = i
    for (let j = 1; j <= n; j++) {
      const cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1
      const insert = (prevRow[j] ?? 0) + 1
      const remove = (row[j - 1] ?? 0) + 1
      const replace = (prevRow[j - 1] ?? 0) + cost
      row[j] = Math.min(insert, remove, replace)
    }
  }
  return (dp[m] as number[])[n] as number
}

function isSubsequence(text: string, query: string) {
  let ti = 0, qi = 0
  while (ti < text.length && qi < query.length) {
    if (text[ti] === query[qi]) qi++
    ti++
  }
  return qi === query.length
}

function fuzzyMatch(rawText: any, rawQuery: any) {
  const text = String(rawText || '').toLowerCase()
  const query = String(rawQuery || '').toLowerCase()
  if (!query) return true
  if (!text) return false
  if (text.includes(query)) return true
  if (isSubsequence(text, query)) return true
  if (query.length >= 4) {
    const threshold = Math.max(1, Math.floor(query.length / 5))
    try { return levenshtein(text, query) <= threshold } catch { return text.includes(query) }
  }
  return false
}

const filtered = computed<any[]>(() => {
  const k = keyword.value.trim().toLowerCase()
  // const t = typeFilter.value // Removed
  // const devFilter = deviceFilter.value // Removed
  // const cat = categoryFilter.value // Removed
  // const sort = sortSelect.value // Removed

  return (tree.value || [])
    .map((m: any) => {
        // Filter by Model Type (Removed from UI)
        // if (t && m.type !== t) return null

        const devGroups = (m.children || []).map((dev: any) => {
            // if (devFilter && dev.deviceType !== devFilter) return null

            const versions = (dev.children || []).filter((v: any) => {
                // Dataset filter removed
                
                // Compression filter removed
                // const isCompressed = v.compressed === true
                // if (cat === '压缩模型' && !isCompressed) return false
                // if (cat === '原始模型' && isCompressed) return false
                
                const matchKw = !k || 
                    fuzzyMatch(m.name, k) || 
                    fuzzyMatch(dev.deviceType, k) || 
                    fuzzyMatch(v.name, k) || 
                    fuzzyMatch(v.dataset, k) 
                
                return matchKw
            })

            if (versions.length === 0) return null

            // Sort versions removed (default order)
            // versions.sort(...)

            const processedVersions = versions.map((v: any) => {
                if (v.type === 'Surrogate' || v.name.startsWith('Surrogate-')) {
                     const clusterCount = v.clusterCount !== undefined ? v.clusterCount : (v.children || []).length
                     return { ...v, children: null, clusterCount }
                }
                return v
            })

            return { ...dev, children: processedVersions }
        }).filter(Boolean)

        if (devGroups.length === 0) return null
        return { ...m, children: devGroups }
    }).filter(Boolean)
})

function resetFilters() {
  keywordInput.value = ''
  keyword.value = ''
  // typeFilter.value = ''
  // datasetFilter.value = '' // Removed
  // deviceFilter.value = ''
  // categoryFilter.value = ''
  // sortSelect.value = ''
  loadModels()
}

function renderNodeCell(record: any) {
  // Level 1: Model
  if (record.level === 1) {
    const typeTag = h(Tag, { color: record.type === 'DNN' ? 'blue' : 'purple' }, { default: () => (record.type === 'DNN' ? 'DNN' : '代理模型') })
    const modelFlops = (record.modelFlops !== undefined && record.modelFlops !== null) ? formatFlops(record.modelFlops) : '-'
    const task = record.taskType || taskTypeMap[record.name] || '未知'
    const io = `输入: ${record.inputDim || '-'}  输出: ${record.outputDim || '-'}`
    
    // Collect unique datasets from all children
    const datasets = new Set<string>()
    if (record.children) {
      for (const dev of record.children) {
        if (dev.children) {
          for (const v of dev.children) {
            if (v.dataset) datasets.add(v.dataset)
          }
        }
      }
    }
    const datasetTags = Array.from(datasets).map(ds => h(Tag, { color: 'cyan' }, { default: () => ds }))

    const row = h('div', { style: 'display:flex;gap:8px;align-items:center;color:#334155;flex-wrap:wrap;' }, [
      typeTag,
      ...datasetTags,
      h('span', {}, `任务: ${task}`),
      h('span', {}, `FLOPs: ${modelFlops}`),
      h('span', {}, io),
      h('span', {}, `创建人: ${record.createdBy || '未知'}`),
      h(Button, { type: 'link', style: 'margin-left:auto;padding:0;margin-right:12px;', onClick: () => {
          const firstDataset = datasetTags.length > 0 ? Array.from(datasets)[0] : undefined
          openCreateWithContext({ 
              mode: 'upload', 
              modelName: record.name,
              taskType: record.taskType || taskTypeMap[record.name] || 'Image Classification',
              datasetName: firstDataset
          })
      } }, { default: () => '添加适配设备类型' }),
      h(Button, { type: 'link', danger: true, style: 'padding:0;', onClick: async () => {
        try {
          const res = await fetch(`/api/models/by_name/${encodeURIComponent(record.name)}`, { method: 'DELETE' })
          const json = await res.json()
          if (json?.code === 0) { message.success('已删除模型'); await loadModels() } else { message.error(json?.message || '删除失败') }
        } catch { message.error('删除失败') }
      } }, { default: () => '删除模型' }),
    ])
    return h('div', {}, [
      h('div', { style: 'font-weight:600;margin-bottom:4px;' }, record.name),
      row,
    ])
  }
  // Level 2: Device Group
  if (record.level === 2) {
       return h('div', {}, [
         h(Tag, { color: 'geekblue' }, { default: () => record.deviceType }),
       ])
  }
  // Level 3: Leaf (Version or Task Group)
  if (record.level === 3) {
    const parts = [] as any[]
    
    // Version Name
    parts.push(h('span', { style: 'font-weight:500;margin-right:8px' }, record.name))
    
    // Only show accuracy if present
    if (record.datasetAccuracy) {
         parts.push(h('span', { style: 'color:#64748b;margin-right:8px;font-size:12px' }, `(${record.datasetAccuracy})`))
    }

    if (record.type === 'Surrogate' || record.name.startsWith('Surrogate-')) {
        // Proxy Model - Hide FLOPs/Latency, show "Proxy" tag
        parts.push(h(Tag, { color: 'purple', style: 'margin-left:8px' }, { default: () => '代理模型' }))
        
        if (record.clusterCount !== undefined) {
             parts.push(h(Tag, { color: 'cyan', style: 'margin-left:8px' }, { default: () => `${record.clusterCount} 个设备簇` }))
        }

        // Always show "View Details" button, handle missing ID in click
        parts.push(h('span', {
            class: 'ant-btn ant-btn-link',
            style: 'margin-left:12px;padding:0;cursor:pointer;',
            onClick: (e: Event) => {
                e.preventDefault()
                e.stopPropagation()
                if (record.sourceTaskId) {
                    // Use state to pass params, aligned with "Create Task" behavior
                    router.push({ 
                        path: '/surrogate-task', 
                        state: { viewTaskId: record.sourceTaskId } 
                    })
                } else {
                    message.warning('该条目缺少关联的任务ID，无法查看详情')
                }
            }
        }, '查看详情'))
    } else {
        // DNN Model
        if (record.flops !== undefined) parts.push(h('span', {}, `FLOPs: ${formatFlops(record.flops)}`))
        // if (record.avgLatencyMs !== undefined) parts.push(h('span', { style: 'margin-left:8px' }, `延迟: ${record.avgLatencyMs} ms`))
        // if (record.avgLatencyMs !== undefined) parts.push(h('span', { style: 'margin-left:8px' }, `延迟: ${record.avgLatencyMs} ms`))

        if (record.compressed !== undefined) parts.push(h(Tag, { color: record.compressed ? 'green' : 'volcano', style: 'margin-left:8px' }, { default: () => (record.compressed ? '压缩' : '未压缩') }))
    }

    if (record.time) parts.push(h('span', { style: 'margin-left:8px;color:#64748b' }, record.time))
    
    parts.push(
        h(Button, {
          type: 'link',
          danger: true,
          style: 'margin-left:12px;padding:0;',
          onClick: async () => {
            try {
              const res = await fetch(`/api/models/perf/${record.id}`, { method: 'DELETE' })
              const json = await res.json()
              if (json?.code === 0) { message.success('已删除记录'); await loadModels() } else { message.error(json?.message || '删除失败') }
            } catch { message.error('删除失败') }
          }
        }, { default: () => '删除' })
    )
    return h('div', {}, parts)
  }
  
  // Level 4: Cluster Info
  if (record.level === 4) {
      return h(Tag, { color: 'blue' }, { default: () => record.name })
  }
  
  return ''
}

function renderDetailCell(record: any) {
  // 提升信息密度：根据节点聚合统计
  try {
    if (record.level === 1) {
      // Model Level
      const devGroups = record.children || []
      const deviceTypes = new Set<string>()
      const versions = [] as any[]
      const datasets = new Set<string>()

      for (const dev of devGroups) {
          if (dev.deviceType) deviceTypes.add(dev.deviceType)
          for (const v of (dev.children || [])) {
              versions.push(v)
              // if (v.dataset) datasets.add(v.dataset) // Removed dataset counting
          }
      }
      
      const compCount = versions.filter(v => v.compressed === true).length
      return `设备型号数: ${deviceTypes.size} | 版本数: ${versions.length} | 压缩: ${compCount}`
    }
    
    if (record.level === 2) {
      // Device Group Level
      const versions = record.children || []
      const latencyVals = versions.map((v: any) => v.avgLatencyMs).filter((x: any) => typeof x === 'number')
      const latencyAvg = latencyVals.length ? (latencyVals.reduce((a: number, b: number) => a + b, 0) / latencyVals.length).toFixed(3) : '-'
      return `版本数: ${versions.length} | 平均延迟: ${latencyAvg} ms`
    }
    
    // Level 3: Leaf
    if (record.level === 3) {
      // return `FLOPs: ${record.flops ?? '-'} | 延迟: ${record.avgLatencyMs ?? '-'} ms`
      return '' // Hidden as requested
    }
  } catch {}
  return ''
}

const columns = [
  { title: '模型列表', key: 'node', customRender: ({ record }: any) => renderNodeCell(record) },
  { title: '详情', key: 'detail', customRender: ({ record }: any) => renderDetailCell(record) },
]

function onCreate() {
  compressModalRef.value?.show({ mode: 'upload' })
}

const formatFlops = (flops: any) => {
  if (!flops) return ''
  const num = Number(flops)
  if (isNaN(num)) return flops
  if (num >= 1e9) return (num / 1e9).toFixed(2) + ' G'
  if (num >= 1e6) return (num / 1e6).toFixed(2) + ' M'
  return num + ' FLOPs'
}

function openCreateWithContext(ctx: { modelName?: string; datasetName?: string; deviceType?: string; taskType?: string; mode?: 'upload' | 'select' }) {
  compressModalRef.value?.show(ctx)
}
</script>

<template>
  <div class="model-page p-5">
    <Card class="summary">
      <div class="summary-header">模型库概览</div>
      <Row :gutter="16">
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-blue-50 cursor-pointer hover:shadow-md transition-shadow" @click="typeFilter = ''">
            <Statistic title="模型总数" :value="totalModels" :value-style="{ color: '#1d4ed8' }">
              <template #prefix><AppstoreOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-sky-50 cursor-pointer hover:shadow-md transition-shadow" @click="typeFilter = 'DNN'">
            <Statistic title="DNN模型" :value="dnnTotal" :value-style="{ color: '#0ea5e9' }">
              <template #prefix><CodeSandboxOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-purple-50 cursor-pointer hover:shadow-md transition-shadow" @click="typeFilter = 'Surrogate'">
            <Statistic title="代理模型" :value="surrogateTotal" :value-style="{ color: '#9333ea' }">
              <template #prefix><DeploymentUnitOutlined /></template>
            </Statistic>
          </Card>
        </Col>
        <Col :xs="12" :sm="12" :md="6" :lg="6">
          <Card :bordered="false" class="stat-box bg-green-50 cursor-pointer hover:shadow-md transition-shadow" @click="categoryFilter = '压缩模型'">
            <Statistic title="压缩模型" :value="compressedCount" :value-style="{ color: '#16a34a' }">
              <template #prefix><FileZipOutlined /></template>
            </Statistic>
          </Card>
        </Col>
      </Row>
    </Card>
    <Card class="table-card">
      <div class="toolbar-row">
        <div class="toolbar-left">
          <Tooltip title="按模型系列、数据集或设备类型关键字过滤">
            <Input
              v-model:value="keywordInput"
              placeholder="搜索模型或设备"
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
          <Button type="primary" @click="onCreate">
            <template #icon><PlusOutlined /></template>
            新增
          </Button>
        </div>
      </div>
      <Table
        :columns="columns"
        :data-source="filtered"
        :pagination="{ pageSize: 8 }"
        :rowKey="(r:any)=>r.id"
        :expandable="{ defaultExpandAllRows: true }"
      />
      <StartCompressModal ref="compressModalRef" />
    </Card>
  </div>
  </template>

<style scoped>
.model-page { display: grid; gap: 8px; }
.summary-header { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.toolbar { }
.toolbar-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar-left { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.toolbar-right { display: flex; align-items: center; }
.classification { font-size: 14px; color: #334155; }
.classify-title { font-weight: 600; margin-bottom: 4px; }
  .table-card { padding-top: 8px; }
.stat-box { border-radius: 8px; }
.bg-blue-50 { background-color: #eff6ff; }
.bg-sky-50 { background-color: #f0f9ff; }
.bg-purple-50 { background-color: #faf5ff; }
.bg-green-50 { background-color: #f0fdf4; }
.cursor-pointer { cursor: pointer; }
.transition-shadow { transition: box-shadow 0.3s; }
.hover\:shadow-md:hover { box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
</style>
