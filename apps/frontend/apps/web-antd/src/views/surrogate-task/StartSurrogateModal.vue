<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { Modal, Steps, Form, Input, Select, Upload, Button, message, Radio, Card, Result, Tag, InputNumber, Divider } from 'ant-design-vue'
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
const { existingModels, deviceTypes, loadData, formatFlops } = useModelData()
const deviceList = ref<any[]>([])

const loadDevices = async () => {
    try {
        const res = await fetch('/api/devices/metrics')
        const json = await res.json()
        deviceList.value = json?.data?.items || json?.items || []
    } catch {}
}

// Form State
const mode = ref<'select' | 'upload'>('select')

const formState = reactive({
  // Step 1: Model
  selectedModelKey: undefined as string | undefined,
  newModelName: '',
  newModelFile: [] as any[],
  modelDefFile: [] as any[],
  inferenceScript: [] as any[],
  taskType: 'Image Classification',
  dataset: '',
  
  // Step 2: Config
  taskName: '',
  targetDevice: undefined as string | undefined,
  targetDeviceList: [] as string[],
  
  // Clustering Params (DBSCAN)
  eps: 0.5,
  minSamples: 5,
  
  // Sampling Params
  sampleSize: 100,
  
  // Training Params (GBRT)
  nEstimators: 100,
  learningRate: 0.1,
  maxDepth: 3,
})

const steps = [
  { title: '选择模型', description: '选择现有或上传新模型' },
  { title: '构建配置', description: '设置聚类、采集与训练参数' },
  { title: '完成', description: '任务已创建' },
]

const forceUploadMode = ref(false)
const uploadOnlyMode = ref(false)

const show = (initialState?: { modelName?: string, datasetName?: string, mode?: 'select' | 'upload' }) => {
  open.value = true
  currentStep.value = 0
  
  if (initialState?.mode === 'upload') {
    mode.value = 'upload'
    forceUploadMode.value = true
    uploadOnlyMode.value = true
  } else {
    mode.value = 'select'
    forceUploadMode.value = false
    uploadOnlyMode.value = false
  }

  formState.selectedModelKey = undefined
  formState.newModelName = ''
  formState.newModelFile = []
  formState.dataset = ''
  formState.taskName = ''
  
  // Reset Config
  formState.eps = 0.5
  formState.minSamples = 5
  formState.sampleSize = 100
  formState.nEstimators = 100
  formState.learningRate = 0.1
  formState.maxDepth = 3

  loadDevices()
  loadData().then(() => {
    if (initialState?.modelName) {
      if (initialState.datasetName) {
        const exactMatch = existingModels.value.find(m => m.label === initialState.modelName && m.dataset === initialState.datasetName)
        if (exactMatch) {
          formState.selectedModelKey = exactMatch.key
          return
        }
      }
      const nameMatch = existingModels.value.find(m => m.label === initialState.modelName)
      if (nameMatch) {
        formState.selectedModelKey = nameMatch.key
      }
    }
  })
}

const handleNext = async () => {
  if (currentStep.value === 0) {
    // Validation
    if (mode.value === 'select' && !formState.selectedModelKey) {
      message.error('请选择一个模型')
      return
    }
    if (mode.value === 'upload') {
      if (!formState.newModelName) {
        message.error('请输入模型名称')
        return
      }
      if (!formState.dataset) {
        message.error('请输入数据集名称')
        return
      }
      if (formState.newModelFile.length === 0) {
        message.error('请上传模型权重文件')
        return
      }
      if (formState.modelDefFile.length === 0) {
        message.error('请上传模型定义文件')
        return
      }
    }
    
    // Auto-generate Task Name
    let modelName = ''
    let datasetName = ''
    
    if (mode.value === 'select') {
        const selected = existingModels.value.find(m => m.key === formState.selectedModelKey)
        modelName = selected?.label || 'Model'
        datasetName = selected?.dataset || ''
    } else {
        modelName = formState.newModelName
        datasetName = formState.dataset
    }
    
    // If uploadOnlyMode, submit immediately (Mock)
    if (uploadOnlyMode.value) {
        await submitTask()
        return
    }

    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    const cleanDs = datasetName.replace(/[^a-zA-Z0-9]/g, '')
    formState.taskName = `Surrogate-${modelName}-${cleanDs}-${dateStr}`
    
    currentStep.value = 1
  } else if (currentStep.value === 1) {
    // Submit
    if (!formState.taskName) {
      message.error('请输入任务名称')
      return
    }
    if (!formState.targetDevice) {
      message.error('请选择目标设备')
      return
    }
    
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

    let modelName = ''
    if (mode.value === 'select') {
        const selected = existingModels.value.find(m => m.key === formState.selectedModelKey)
        modelName = selected?.label || 'Model'
    } else {
        modelName = formState.newModelName
    }

    if (!formState.targetDeviceList || formState.targetDeviceList.length === 0) {
        message.error('请至少选择一个参与设备')
        return
    }

    // Construct Payload for /api/surrogate/pipelines
    const payload = {
        taskName: formState.taskName,
        modelName: modelName,
        deviceType: formState.targetDevice,
        deviceList: formState.targetDeviceList,
        // Detailed Params
        // Clustering (DBSCAN)
        eps: formState.eps,
        min_samples: formState.minSamples,
        // Sampling
        sampleSize: formState.sampleSize,
        // GBRT
        n_estimators: formState.nEstimators,
        learning_rate: formState.learningRate,
        max_depth: formState.maxDepth,
    }

    const res = await fetch('/api/surrogate/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    const json = await res.json()
    
    if (json.code !== 0) {
        throw new Error(json.message || '创建失败')
    }

    createdTaskId.value = json.data?.id
    message.success('代理模型构建任务创建成功')
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
        const res = await fetch(`/api/surrogate/pipelines/${createdTaskId.value}/start`, {
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
    router.push('/surrogate-task')
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
  const templateContent = `# HDAP Platform Standard Inference Script
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
    :title="uploadOnlyMode ? '上传新模型' : '创建代理模型构建任务'"
    :width="700"
    :footer="null"
    :maskClosable="false"
  >
    <div class="wizard-content">
      <Steps v-if="!uploadOnlyMode" :current="currentStep" :items="steps" class="mb-8" />

      <!-- Step 1: Model Selection -->
      <div v-if="currentStep === 0" class="step-panel">
        <div v-if="!forceUploadMode" class="mode-switch mb-6">
          <Radio.Group v-model:value="mode" button-style="solid" size="large">
            <Radio.Button value="select">选择现有模型</Radio.Button>
            <Radio.Button value="upload">上传新模型</Radio.Button>
          </Radio.Group>
        </div>

        <div v-if="mode === 'select'" class="select-mode">
          <Form layout="vertical">
            <Form.Item label="选择模型" required help="从模型库中选择一个已有的DNN模型">
              <Select 
                v-model:value="formState.selectedModelKey" 
                placeholder="请选择模型"
                show-search
                option-filter-prop="label"
                option-label-prop="label"
                size="large"
              >
                <Select.Option v-for="item in existingModels" :key="item.key" :value="item.key" :label="item.label">
                  <div class="flex flex-col w-full py-1">
                    <span class="font-medium text-base mb-1">{{ item.label }}</span>
                    <div class="flex flex-wrap items-center gap-2">
                      <Tag :color="item.type === 'DNN' ? 'blue' : 'purple'">{{ item.type }}</Tag>
                      <span class="text-xs text-gray-500">任务: {{ item.taskType }}</span>
                      <span v-if="item.modelFlops" class="text-xs text-gray-500">FLOPs: {{ formatFlops(item.modelFlops) }}</span>
                      <Tag v-if="item.dataset && item.dataset !== '-'" color="cyan">{{ item.dataset }}</Tag>
                      <span v-if="item.accuracy && item.accuracy !== '-'" class="text-xs text-gray-500">精度: {{ item.accuracy }}</span>
                    </div>
                  </div>
                </Select.Option>
              </Select>
            </Form.Item>
          </Form>
        </div>

        <div v-if="mode === 'upload'" class="upload-mode">
          <Form layout="vertical">
            <Form.Item label="模型名称" required>
              <Input v-model:value="formState.newModelName" placeholder="例如：My-ResNet50" size="large" />
            </Form.Item>
            <Form.Item label="任务类型">
              <Select v-model:value="formState.taskType" size="large">
                <Select.Option value="Image Classification">图像分类</Select.Option>
                <Select.Option value="Object Detection">目标检测</Select.Option>
                <Select.Option value="Segmentation">语义分割</Select.Option>
              </Select>
            </Form.Item>
            
            <div class="grid grid-cols-2 gap-4">
              <Form.Item label="模型权重文件 (.pth)" required class="col-span-2">
                <Upload.Dragger
                  v-model:fileList="formState.newModelFile"
                  name="modelFile"
                  :multiple="false"
                  :before-upload="() => false"
                  @change="handleUploadChange"
                >
                  <p class="ant-upload-drag-icon text-gray-400">
                    <InboxOutlined class="text-2xl" />
                  </p>
                  <p class="ant-upload-text text-sm">点击或拖拽模型权重文件</p>
                </Upload.Dragger>
              </Form.Item>
              
              <Form.Item label="模型定义文件 (.py)" required>
                <Upload.Dragger
                  v-model:fileList="formState.modelDefFile"
                  name="defFile"
                  :multiple="false"
                  :before-upload="() => false"
                >
                  <p class="ant-upload-drag-icon text-gray-400">
                    <DeploymentUnitOutlined class="text-2xl" />
                  </p>
                  <p class="ant-upload-text text-sm">点击或拖拽定义文件</p>
                </Upload.Dragger>
              </Form.Item>

              <Form.Item required>
                <template #label>
                  <div class="flex items-center">
                    <span>推理脚本 (.py)</span>
                    <a @click.prevent="downloadTemplate" class="text-blue-500 text-xs flex items-center hover:underline cursor-pointer ml-2" style="font-weight: normal">
                      <DownloadOutlined class="mr-1"/> 下载模版
                    </a>
                  </div>
                </template>
                <Upload.Dragger
                  v-model:fileList="formState.inferenceScript"
                  name="scriptFile"
                  :multiple="false"
                  :before-upload="() => false"
                >
                  <p class="ant-upload-drag-icon text-gray-400">
                    <FileTextOutlined class="text-2xl" />
                  </p>
                  <p class="ant-upload-text text-sm">点击或拖拽推理脚本</p>
                </Upload.Dragger>
              </Form.Item>
            </div>
            
            <Form.Item label="数据集" required>
              <Input v-model:value="formState.dataset" placeholder="例如：/data/datasets/imagenet" size="large" />
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
          
          <Form.Item label="目标设备类型" required>
            <Select v-model:value="formState.targetDevice" :options="deviceTypes" size="large" />
          </Form.Item>

          <Form.Item label="选择参与设备" required help="必须选择至少一个设备">
            <Select 
                v-model:value="formState.targetDeviceList" 
                mode="multiple" 
                placeholder="选择具体设备IP" 
                style="width: 100%"
                :max-tag-count="3"
            >
                <Select.Option v-for="d in deviceList.filter(x => !formState.targetDevice || x.type === formState.targetDevice)" :key="d.ip" :value="d.ip">
                    {{ d.ip }} ({{ d.status }})
                </Select.Option>
            </Select>
          </Form.Item>

          <Divider orientation="left" style="font-size:14px;color:#1890ff">聚类参数 (DBSCAN)</Divider>
          <div class="grid grid-cols-2 gap-4">
            <Form.Item label="Epsilon (eps)" help="DBSCAN聚类半径">
              <InputNumber v-model:value="formState.eps" :step="0.1" style="width:100%" />
            </Form.Item>
            <Form.Item label="Min Samples" help="DBSCAN最小样本数">
              <InputNumber v-model:value="formState.minSamples" :min="1" style="width:100%" />
            </Form.Item>
          </div>

          <Divider orientation="left" style="font-size:14px;color:#1890ff">采样参数</Divider>
          <Form.Item label="DNN模型随机采样次数" help="设置数据采集阶段的随机采样规模">
            <InputNumber v-model:value="formState.sampleSize" :min="1" style="width:100%" />
          </Form.Item>

          <Divider orientation="left" style="font-size:14px;color:#1890ff">训练参数 (GBRT)</Divider>
          <div class="grid grid-cols-3 gap-4">
            <Form.Item label="弱学习器数量 (n_estimators)">
              <InputNumber v-model:value="formState.nEstimators" :min="1" style="width:100%" />
            </Form.Item>
            <Form.Item label="学习率 (learning_rate)">
              <InputNumber v-model:value="formState.learningRate" :min="0.001" :step="0.01" style="width:100%" />
            </Form.Item>
            <Form.Item label="最大深度 (max_depth)">
              <InputNumber v-model:value="formState.maxDepth" :min="1" style="width:100%" />
            </Form.Item>
          </div>

        </Form>
      </div>

      <!-- Step 3: Success -->
      <div v-if="currentStep === 2" class="step-panel flex flex-col items-center justify-center py-8">
        <Result
          status="success"
          title="代理模型构建任务已创建"
          sub-title="任务已创建成功。您可以点击“执行任务”立即启动任务，或稍后在任务列表中手动启动。"
        >
          <template #extra>
            <Button type="primary" key="start" @click="handleStartTask" :loading="loading">执行任务</Button>
            <Button key="view" @click="handleViewTask">查看任务</Button>
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
.mt-4 { margin-top: 16px; }
.text-xs { font-size: 12px; }
.text-gray-500 { color: #6b7280; }
</style>
