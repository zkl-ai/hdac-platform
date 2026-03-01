<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { Modal, Steps, Form, Input, Select, Upload, Button, message, Radio, Result, InputNumber, Divider, Switch, Tag } from 'ant-design-vue'
import { InboxOutlined, DeploymentUnitOutlined, FileTextOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import type { UploadChangeParam } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useModelData } from '#/composables/useModelData'

const props = defineProps<{
  onSuccess?: () => void
}>()

const router = useRouter()
const open = ref(false)
const currentStep = ref(0)
const loading = ref(false)
const createdTaskId = ref<number | null>(null)

// Data Sources
const { modelTree, deviceTypes, loadData, formatFlops } = useModelData()
const deviceList = ref<{ label: string; value: string; type: string }[]>([])

// Form State
const mode = ref<'select' | 'upload'>('select')

const formState = reactive({
  // Step 1: Selection
  // modelType: 'DNN' as 'DNN' | 'Surrogate', // Deprecated
  targetDeviceType: undefined as string | undefined,
  selectedModelName: undefined as string | undefined,
  selectedVersionId: undefined as number | undefined,
  
  // Upload New (Deprecated)
  newModelName: '',
  newModelFile: [] as any[],
  modelDefFile: [] as any[],
  inferenceScript: [] as any[],
  taskType: 'Image Classification',
  dataset: '',
  
  // Step 2: Config
  taskName: '',
  grayRatio: 20,
  deviceSubset: [] as string[], // Selected device IDs
  evalWindowType: 'time' as 'time' | 'rounds',
  evalWindowValue: 60,
})

const steps = [
  { title: '选择模型', description: '选择版本' },
  { title: '部署配置', description: '设置灰度参数' },
  { title: '完成', description: '任务已创建' },
]

const forceUploadMode = ref(false)
const uploadOnlyMode = ref(false)

// 1. Available Models (All DNN Models)
const availableModels = computed(() => {
    return (modelTree.value || [])
        //.filter((m: any) => m.type === 'DNN') // User said "we only deploy DNN models", so maybe filter? Or just show all.
        // Actually, let's show all but maybe user knows what they are doing.
        // The user prompt said: "I mean different DNN models (resnet50, vgg...)".
        // It implies the list should be models.
        .map((m: any) => ({
            label: m.name,
            value: m.name,
            type: m.type
        }))
})

// 2. Available Device Types (based on Selected Model)
const availableDeviceTypes = computed(() => {
    const mName = formState.selectedModelName
    if (!mName) return []
    
    const types = new Set<string>()
    const modelNode = (modelTree.value || []).find((m: any) => m.name === mName)
    
    if (modelNode && modelNode.children) {
        modelNode.children.forEach((dev: any) => {
             // Only add device types that have actual versions
             if (dev.children && dev.children.length > 0) {
                 if (dev.deviceType) types.add(dev.deviceType)
             }
        })
    }
    return Array.from(types).map(t => ({ label: t, value: t }))
})

// 3. Available Versions (based on Model AND Device Type)
const availableVersions = computed(() => {
    const mName = formState.selectedModelName
    const dType = formState.targetDeviceType
    if (!mName || !dType) return []

    const modelNode = (modelTree.value || []).find((m: any) => m.name === mName)
    if (!modelNode || !modelNode.children) return []

    const deviceNode = modelNode.children.find((d: any) => d.deviceType === dType)
    if (!deviceNode || !deviceNode.children) return []

    return deviceNode.children
        .map((v: any) => ({
            label: v.name,
            value: v.id,
            dataset: v.dataset,
            accuracy: v.datasetAccuracy,
            flops: v.flops,
            latency: v.avgLatencyMs,
            compressed: v.compressed,
            type: v.type
        }))
})

// Watchers to reset downstream selections
watch(() => formState.selectedModelName, () => {
    formState.targetDeviceType = undefined
    formState.selectedVersionId = undefined
})
watch(() => formState.targetDeviceType, () => {
    formState.selectedVersionId = undefined
})

// Filter devices for Step 2
const filteredDevices = computed(() => {
    if (!formState.targetDeviceType) return []
    return deviceList.value.filter(d => d.type === formState.targetDeviceType)
})

const loadDevices = async () => {
    try {
        const res = await fetch('/api/devices/metrics')
        const json = await res.json()
        const items = json?.data?.items || json?.items || []
        deviceList.value = items.map((d: any) => {
            const val = d.id || d.ip || `unknown-${Math.random().toString(36).substr(2, 9)}`;
            const name = d.name || d.id || 'Unnamed Device';
            const ip = d.ip || 'Unknown IP';
            
            return {
                label: `${name} (${ip})`,
                value: val,
                type: d.type
            };
        })
    } catch (e) {
        console.error('Failed to load devices', e);
    }
}

const show = (initialState?: { mode?: 'select' | 'upload' }) => {
  open.value = true
  currentStep.value = 0
  
  if (initialState?.mode === 'upload') {
    // Mode 'upload' is no longer supported for this modal, fallback to select
    mode.value = 'select'
    forceUploadMode.value = false
    uploadOnlyMode.value = false
  } else {
    mode.value = 'select'
    forceUploadMode.value = false
    uploadOnlyMode.value = false
  }

  // Reset
  // formState.modelType = 'DNN' // Deprecated
  formState.selectedModelName = undefined
  formState.targetDeviceType = undefined
  formState.selectedVersionId = undefined
  
  formState.newModelName = ''
  formState.newModelFile = []
  formState.dataset = ''
  formState.taskName = ''
  formState.deviceSubset = []
  
  loadData()
  loadDevices()
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    // Validation
    if (mode.value === 'select') {
        if (!formState.selectedModelName) { message.error('请选择模型'); return }
        if (!formState.targetDeviceType) { message.error('请选择设备类型'); return }
        if (!formState.selectedVersionId) { message.error('请选择版本'); return }
    }
    // Upload mode removed validation
    
    // Auto-generate Task Name
    let modelName = ''
    let datasetName = ''
    
    if (mode.value === 'select') {
        modelName = formState.selectedModelName || 'Model'
        // Try to get dataset from version
        const v = availableVersions.value.find(v => v.value === formState.selectedVersionId)
        datasetName = v?.dataset || ''
    }
    
    if (uploadOnlyMode.value) {
        await submitTask()
        return
    }

    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    const cleanDs = datasetName.replace(/[^a-zA-Z0-9]/g, '')
    formState.taskName = `GrayDeploy-${modelName}-${cleanDs}-${dateStr}`
    
    currentStep.value = 1
  } else if (currentStep.value === 1) {
    // Submit
    if (!formState.taskName) { message.error('请输入任务名称'); return }
    if (formState.deviceSubset.length === 0) { message.error('请至少选择一个灰度设备'); return }
    
    await submitTask()
  }
}

const handlePrev = () => {
  currentStep.value--
}

const submitTask = async () => {
  loading.value = true
  try {
    if (uploadOnlyMode.value) {
        await new Promise(resolve => setTimeout(resolve, 1000))
        message.success('模型上传成功')
        open.value = false
        props.onSuccess?.()
        return
    }

    let candidateModel = ''
    let deviceType = ''
    
    if (mode.value === 'select') {
        candidateModel = formState.selectedModelName || ''
        deviceType = formState.targetDeviceType || ''
    } else {
        candidateModel = formState.newModelName
        // For upload mode, we might not have device type set if we skipped step 1 selection
        // But step 2 requires device type for subset selection.
        // Wait, in upload mode, step 1 has no device selection.
        // Step 2 needs device type.
        // So in upload mode, we need to ask for device type in Step 2.
        // Current implementation: formState.targetDeviceType is used in Step 1.
        // In Upload mode, we don't set it in Step 1.
        // So Step 2 needs to allow selecting device type if not set.
    }
    
    // NOTE: Current Step 2 UI uses `formState.deviceType` (old prop) but I changed it to `targetDeviceType` in Step 1.
    // I should align them.
    // Let's assume for Select Mode, targetDeviceType is already set.
    // For Upload Mode, we need to let user select it in Step 2.
    
    const payload = {
        name: formState.taskName,
        modelName: candidateModel,
        deviceType: deviceType || formState.targetDeviceType, // Fallback
        candidateModel: candidateModel,
        versionId: formState.selectedVersionId, // Send version ID
        grayRatio: formState.grayRatio,
        deviceSubset: formState.deviceSubset.join(','),
        evalWindowType: formState.evalWindowType,
        evalWindowValue: formState.evalWindowValue
    }

    const res = await fetch('/api/deploy/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    const json = await res.json()
    
    if (json.code !== 0) {
        throw new Error(json.message || '创建失败')
    }

    createdTaskId.value = json.data?.id
    message.success('DNN模型部署任务创建成功')
    currentStep.value = 2
    props.onSuccess?.()
  } catch (e: any) {
    message.error(e.message || '任务创建失败')
  } finally {
    loading.value = false
  }
}

const handleStartTask = async () => {
    if (!createdTaskId.value) return
    loading.value = true
    try {
        const res = await fetch(`/api/deploy/tasks/${createdTaskId.value}/start`, {
            method: 'POST'
        })
        const json = await res.json()
        if (json.code === 0) {
            message.success('任务已开始执行')
            open.value = false
            props.onSuccess?.()
        } else {
            message.error(json.message || '启动失败')
        }
    } catch (e) {
        message.error('启动失败')
    } finally {
        loading.value = false
    }
}

const handleViewTask = () => {
    open.value = false
    props.onSuccess?.()
}

const handleClose = () => {
    open.value = false
}

// Upload Handler
const handleUploadChange = (info: UploadChangeParam) => {
  let fileList = [...info.fileList];
  fileList = fileList.slice(-1);
  formState.newModelFile = fileList;
};

const downloadTemplate = () => {
  const templateContent = `# Inference Script Template
import torch
def get_input_shape(): return (1, 3, 224, 224)
def load_model(path): pass
`
  const blob = new Blob([templateContent], { type: 'text/plain' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'inference_template.py'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

defineExpose({ show })
</script>

<template>
  <Modal
    v-model:open="open"
    :title="uploadOnlyMode ? '上传新模型' : '新建DNN模型部署任务'"
    :width="700"
    :footer="null"
    :maskClosable="false"
  >
    <div class="wizard-content">
      <Steps v-if="!uploadOnlyMode" :current="currentStep" :items="steps" class="mb-8" />

      <!-- Step 1: Candidate Model Selection -->
      <div v-if="currentStep === 0" class="step-panel">
        <div v-if="mode === 'select'" class="select-mode">
          <Form layout="vertical">
            <Form.Item label="1. 选择模型" required>
              <Select 
                v-model:value="formState.selectedModelName" 
                placeholder="请选择模型"
                show-search
                :options="availableModels"
                size="large"
              />
            </Form.Item>

            <Form.Item label="2. 设备类型" required>
              <Select 
                v-model:value="formState.targetDeviceType" 
                placeholder="请选择设备类型"
                :options="availableDeviceTypes"
                :disabled="!formState.selectedModelName"
                size="large"
              />
            </Form.Item>

            <Form.Item label="3. 选择版本" required>
              <Select 
                v-model:value="formState.selectedVersionId" 
                placeholder="请选择版本"
                size="large"
                :disabled="!formState.targetDeviceType"
              >
                <Select.Option v-for="v in availableVersions" :key="v.value" :value="v.value">
                    <div class="flex items-center justify-between w-full">
                        <span>{{ v.label }}</span>
                        <div class="flex items-center gap-2">
                            <Tag v-if="v.compressed" color="green">压缩</Tag>
                            <Tag v-else color="blue">原始</Tag>
                            <span class="text-gray-400 text-xs">{{ v.dataset }}</span>
                            <span v-if="v.accuracy" class="text-gray-400 text-xs">{{ v.accuracy }}</span>
                        </div>
                    </div>
                </Select.Option>
              </Select>
            </Form.Item>
          </Form>
        </div>
      </div>

      <!-- Step 2: Configuration -->
      <div v-if="currentStep === 1" class="step-panel">
        <Form layout="vertical">
          <Form.Item label="任务名称" required>
            <Input v-model:value="formState.taskName" placeholder="任务名称" size="large" />
          </Form.Item>
          
          <Form.Item label="设备类型" required>
            <Select v-if="mode === 'upload'" v-model:value="formState.targetDeviceType" :options="deviceTypes" size="large" placeholder="选择目标设备类型" />
            <Input v-else v-model:value="formState.targetDeviceType" disabled size="large" />
          </Form.Item>

          <div class="grid grid-cols-2 gap-4">
              <Form.Item label="灰度比例 (%)" help="初始部署的流量或设备比例">
                <InputNumber v-model:value="formState.grayRatio" :min="1" :max="99" style="width:100%" size="large" />
              </Form.Item>
              
              <Form.Item label="评估窗口" help="设置灰度评估的持续时间或轮次，评估通过后将自动扩大部署范围">
               <div style="display:flex;gap:8px">
                  <Select v-model:value="formState.evalWindowType" style="width: 100px" size="large">
                    <Select.Option value="time">时间(min)</Select.Option>
                    <Select.Option value="rounds">轮次</Select.Option>
                  </Select>
                  <InputNumber v-model:value="formState.evalWindowValue" style="flex:1" :min="1" size="large" />
               </div>
              </Form.Item>
          </div>

          <Form.Item label="灰度设备集合" required help="从设备管理列表中选择参与灰度的设备">
             <Select 
                v-model:value="formState.deviceSubset" 
                mode="multiple" 
                placeholder="请先选择设备类型，再选择设备" 
                :options="filteredDevices"
                size="large"
                :disabled="!formState.targetDeviceType"
             />
             <div v-if="!formState.targetDeviceType" class="text-xs text-gray-400 mt-1">请先选择设备类型</div>
             <div v-else-if="filteredDevices.length === 0" class="text-xs text-gray-400 mt-1">该类型下暂无可用设备</div>
          </Form.Item>

        </Form>
      </div>

      <!-- Step 3: Success -->
      <div v-if="currentStep === 2" class="step-panel flex flex-col items-center justify-center py-8">
        <Result
          status="success"
          title="DNN模型部署任务已创建"
          sub-title="任务已加入队列。您可以立即执行或稍后在列表中管理。"
        >
          <template #extra>
            <Button type="primary" key="start" @click="handleStartTask" :loading="loading">执行部署</Button>
            <Button key="view" @click="handleViewTask">查看状态</Button>
            <Button key="close" @click="handleClose">关闭</Button>
          </template>
        </Result>
      </div>

      <!-- Footer Actions -->
      <div class="footer-actions mt-8 flex justify-between" v-if="currentStep < 2">
        <Button size="large" @click="handleClose" v-if="currentStep === 0">取消</Button>
        <Button size="large" @click="handlePrev" v-if="currentStep === 1">上一步</Button>
        
        <Button type="primary" size="large" @click="handleNext" :loading="loading">
          {{ uploadOnlyMode ? '确认上传' : (currentStep === 1 ? '创建任务' : '下一步') }}
        </Button>
      </div>
    </div>
  </Modal>
</template>

<style scoped>
.step-panel {
  min-height: 300px;
}
.mode-switch {
  text-align: center;
}
.mb-8 { margin-bottom: 32px; }
.mb-6 { margin-bottom: 24px; }
.mt-8 { margin-top: 32px; }
.text-xs { font-size: 12px; }
.text-gray-500 { color: #6b7280; }
</style>
