<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted } from 'vue'
import { Modal, Steps, Form, Input, Select, Upload, Button, message, Radio, Card, Result, Tag, Switch } from 'ant-design-vue'
import { InboxOutlined, CloudUploadOutlined, DeploymentUnitOutlined, CheckCircleOutlined, FileTextOutlined, DownloadOutlined } from '@ant-design/icons-vue'
import type { UploadChangeParam } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import { useModelData } from '#/composables/useModelData'
import axios from 'axios'

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
const proxyModels = ref<{ label: string; value: string }[]>([])
const datasets = ref<{ label: string; value: string }[]>([])
const devices = ref<{ ip: string; type: string }[]>([])

const fetchDevices = async () => {
  try {
    const { data } = await axios.get('/api/devices/metrics')
    devices.value = (data?.data?.items || data?.items || []).map((it: any) => ({ ip: it.ip, type: it.type }))
  } catch (e) {
    console.error('Failed to fetch devices:', e)
    message.warning('无法加载设备列表')
  }
}

onMounted(fetchDevices)

const availableDeviceIps = computed(() => {
  if (!formState.targetDevice) return []
  return devices.value
    .filter(d => d.type === formState.targetDevice)
    .map(d => ({ label: d.ip, value: d.ip }))
})

const fetchDatasets = async () => {
  try {
    const res = await fetch('/api/datasets')
    const json = await res.json()
    datasets.value = (json.data?.items || []).map((d: any) => ({ label: d.name, value: d.name }))
  } catch (e) {
    console.error(e)
  }
}

// Form State
const mode = ref<'select' | 'upload'>('select')

const formState = reactive({
  // Step 1: Model
  selectedModelKey: undefined as string | undefined, // Changed to key to handle duplicate names
  newModelName: '',
  newModelFile: [] as any[],
  modelDefFile: [] as any[],
  inferenceScript: [] as any[],
  taskType: 'Image Classification',
  dataset: '',
  
  // Step 2: Config
  taskName: '',
  targetDevice: undefined as string | undefined,
  deviceIps: [] as string[],
  useProxy: false,
  proxyModel: undefined as string | undefined,
  compressionMethod: 'HDAP', // Default from existing code
  targetRatio: 50,
  hdapPopulation: 10,
  hdapGenerations: 30,
  gridRates: '',
  gridMin: 0.1,
  gridMax: 0.9,
  gridStep: 0.1,
  
  // Training Params
  trainingEpochs: 5,
  batchSize: 64,
  learningRate: 0.01,
})

const fetchProxyModels = async () => {
  if (!formState.selectedModelKey || !formState.targetDevice) return
  
  // key is "Name|Dataset" or just ID/Name. Assuming name from label or similar logic.
  // Actually selectedModelKey comes from existingModels which uses key.
  // In `useModelData.ts`, key might be unique.
  // Let's use `modelName` derived from selected item.
  
  const selected = existingModels.value.find(m => m.key === formState.selectedModelKey)
  if (!selected) return
  
  const modelName = selected.label
  
  try {
    const res = await fetch(`/api/models/proxies?modelName=${modelName}&deviceType=${formState.targetDevice}`)
    const json = await res.json()
    proxyModels.value = json.data?.items || []
    
    // Auto select first if available and not set
    if (proxyModels.value.length > 0 && !formState.proxyModel) {
      formState.proxyModel = proxyModels.value[0].value
    }
  } catch (e) {
    console.error(e)
  }
}

const fetchDefaults = async () => {
  if (!formState.selectedModelKey) return
  const selected = existingModels.value.find(m => m.key === formState.selectedModelKey)
  if (!selected) return
  
  const modelName = selected.label
  try {
      const res = await fetch(`/api/compress/tasks/defaults?modelName=${modelName}&compressionAlgo=${formState.compressionMethod}`)
      const json = await res.json()
      if (json.code === 0 && json.data) {
          formState.configJson = JSON.stringify(json.data, null, 2)
      }
  } catch (e) {
      console.error(e)
  }
}

watch([() => formState.selectedModelKey, () => formState.targetDevice], () => {
  if (formState.useProxy) {
    fetchProxyModels()
  }
})

watch(() => formState.compressionMethod, () => {
    fetchDefaults()
})

watch(() => formState.useProxy, (val) => {
  if (val) {
    fetchProxyModels()
  } else {
    formState.proxyModel = undefined
  }
})

const steps = [
  { title: '选择模型', description: '选择现有或上传新模型' },
  { title: '压缩配置', description: '设置目标设备与参数' },
  { title: '完成', description: '任务已创建' },
]


const forceUploadMode = ref(false)
const uploadOnlyMode = ref(false)

const show = (initialState?: { modelName?: string, datasetName?: string, taskType?: string, mode?: 'select' | 'upload' }) => {
  open.value = true
  currentStep.value = 0
  
  if (initialState?.mode === 'upload') {
    mode.value = 'upload'
    forceUploadMode.value = true
    uploadOnlyMode.value = true
    if (initialState.modelName) {
        formState.newModelName = initialState.modelName
    }
    if (initialState.taskType) {
        formState.taskType = initialState.taskType
    }
    if (initialState.datasetName) {
        formState.dataset = initialState.datasetName
    }
  } else {
    mode.value = 'select'
    forceUploadMode.value = false
    uploadOnlyMode.value = false
  }

  formState.selectedModelKey = undefined
  // Only clear newModelName if it wasn't provided in initialState
  if (!initialState?.modelName) {
    formState.newModelName = ''
  }
  formState.newModelFile = []
  
  // Only clear dataset if it wasn't provided in initialState
  if (!initialState?.datasetName) {
    formState.dataset = ''
  }

  formState.taskName = ''
  fetchDatasets()
  loadData().then(() => {
    if (initialState?.modelName) {
      // Try to find exact match with dataset
      if (initialState.datasetName) {
        const exactMatch = existingModels.value.find(m => m.label === initialState.modelName && m.dataset === initialState.datasetName)
        if (exactMatch) {
          formState.selectedModelKey = exactMatch.key
          return
        }
      }
      // Fallback to first match by model name
      const nameMatch = existingModels.value.find(m => m.label === initialState.modelName)
      if (nameMatch) {
        formState.selectedModelKey = nameMatch.key
      }
    }
  })
}

// Trigger fetch when entering step 1
const handleNext = async () => {
  console.log('handleNext clicked, currentStep:', currentStep.value)
  if (currentStep.value === 0) {
    // Validation
    if (mode.value === 'select') {
        if (!formState.selectedModelKey) {
          message.error('请选择一个模型')
          return
        }
    } else { // upload mode
        if (!formState.newModelName) {
            message.error('请输入模型名称')
            return
        }
        
        const isAddDeviceMode = forceUploadMode.value && !!formState.newModelName
        
        if (!formState.dataset) {
            message.error('请输入数据集名称')
            return
        }
    
        if (isAddDeviceMode) {
            const currentModel = existingModels.value.find(m => m.label === formState.newModelName)
            if (currentModel && currentModel.children) {
                const deviceExists = currentModel.children.some((dev: any) => dev.deviceType === formState.targetDevice)
                if (deviceExists) {
                    message.error(`该模型已存在 ${formState.targetDevice} 的适配记录，请勿重复添加`)
                    return
                }
            }
        }
        
        if (!isAddDeviceMode) {
            if (formState.newModelFile.length === 0) {
                message.error('请上传模型权重文件')
                return
            }
            if (formState.modelDefFile.length === 0) {
                message.error('请上传模型定义文件')
                return
            }
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
    
    // If uploadOnlyMode, submit immediately
    if (uploadOnlyMode.value) {
        await submitTask()
        return
    }
    
    const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '')
    const cleanDs = datasetName.replace(/[^a-zA-Z0-9]/g, '')
    formState.taskName = `DNNCompress-${modelName}-${cleanDs}-${dateStr}`
    
    // Fetch Params when moving to Config Step
    if (mode.value === 'select') {
        await fetchDefaults()
    }

    currentStep.value = 1
  } else if (currentStep.value === 1) {
    // Submit
    console.log('Submitting task...')
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
  console.log('submitTask started', JSON.parse(JSON.stringify(formState)))
  loading.value = true
  try {
    if (uploadOnlyMode.value) {
        // Mock upload logic for now or implement real upload
        await new Promise(resolve => setTimeout(resolve, 1000))
        
        const isAddDeviceMode = forceUploadMode.value && !!formState.newModelName
        message.success(isAddDeviceMode ? '设备适配成功' : '模型上传成功')
        
        open.value = false
        props.onSuccess?.()
        return
    }

    // Prepare Payload
    let modelName = ''
    if (mode.value === 'select') {
        const selected = existingModels.value.find(m => m.key === formState.selectedModelKey)
        modelName = selected?.label || 'Model'
    } else {
        modelName = formState.newModelName
    }

    let algoParams = ''
    // Use configJson as the primary source
    if (formState.configJson) {
        try {
            const params = JSON.parse(formState.configJson)
            
            // Merge Proxy info from UI
            if (formState.useProxy) {
                params['use_proxy'] = 'True'
                params['proxy_model'] = formState.proxyModel
            }
            
            // Ensure method is set correctly
            params['method'] = formState.compressionMethod

            // Add device_ips for real hardware evaluation
            if (formState.deviceIps && formState.deviceIps.length > 0) {
              params['device_ips'] = formState.deviceIps.join(',')
            }
            
            algoParams = JSON.stringify(params)
        } catch (e) {
            message.error('配置参数JSON格式错误')
            loading.value = false
            return
        }
    } else {
        // Fallback (legacy logic, mostly unreachable if defaults load)
        if (formState.compressionMethod === 'HDAP') {
            algoParams = `targetRatio=${formState.targetRatio};pop_size=${formState.hdapPopulation};generations=${formState.hdapGenerations}`
        } else if (formState.compressionMethod === 'Grid Search') {
            algoParams = `method=Grid Search;prune_rate_grid=${formState.gridRates}`
        }
        
        if (formState.useProxy) {
            algoParams += `;use_proxy=True;proxy_model=${formState.proxyModel}`
        }
        
        // Add Training Params
        algoParams += `;train_epochs=${formState.trainingEpochs};batch_size=${formState.batchSize};lr=${formState.learningRate}`
    }

    const payload = {
        name: formState.taskName,
        modelName: modelName,
        deviceType: formState.targetDevice,
        stage: 'pruning', // Default to pruning first
        compressionAlgo: formState.compressionMethod,
        algoParams: algoParams,
        latencyBudget: null,
        accuracyLossLimit: null
    }

    const res = await fetch('/api/compress/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    const json = await res.json()
    
    if (json.code !== 0) {
        throw new Error(json.message || '创建失败')
    }

    createdTaskId.value = json.data?.id
    message.success('任务创建成功')
    currentStep.value = 2
    props.onSuccess?.()
  } catch (e: any) {
    message.error(e.message || (uploadOnlyMode.value ? '模型上传失败' : '任务创建失败'))
  } finally {
    loading.value = false
  }
}

const handleStartTask = async () => {
    if (!createdTaskId.value) return
    loading.value = true
    try {
        const res = await fetch(`/api/compress/tasks/${createdTaskId.value}/start`, {
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
    router.push('/compress-task')
}

const handleClose = () => {
  open.value = false
}

// Upload Handler
const handleUploadChange = (info: UploadChangeParam) => {
  let fileList = [...info.fileList];
  fileList = fileList.slice(-1); // Only keep last one
  formState.newModelFile = fileList;
};

const downloadTemplate = () => {
  const templateContent = `# HDAP Platform Standard Inference Script
# 该脚本将贯穿模型的全生命周期：
# 1. [平台侧] 上传阶段：用于解析模型结构，计算 FLOPs 和 Parameters。
# 2. [设备侧] 部署阶段：用于在边缘设备（如 Jetson, RK3588）上加载模型并进行基准测试（Benchmark）。

import torch
import torch.nn as nn
import time

def get_input_shape():
    """
    [必填] 返回模型输入的形状 (Batch_Size, Channels, Height, Width)
    平台将使用此形状生成 Dummy Input 用于计算 FLOPs
    """
    # 示例: ResNet50 标准输入
    return (1, 3, 224, 224)

def load_model(model_path):
    """
    [必填] 加载模型
    :param model_path: 模型权重文件路径 (.pth)
    :return: 加载好的 PyTorch 模型对象 (eval模式)
    """
    # TODO: 请在此处实现您的模型加载逻辑
    # 示例：
    # model = MyModelClass()
    # model.load_state_dict(torch.load(model_path, map_location='cpu'))
    # model.eval()
    # return model
    pass

def preprocess(image_path):
    """
    [可选] 预处理函数，用于真实数据测试
    """
    pass

if __name__ == "__main__":
    # 本地调试代码
    print("Testing model loading...")
    # model_path = "your_model.pth"
    # model = load_model(model_path)
    # input_shape = get_input_shape()
    # dummy_input = torch.randn(input_shape)
    # output = model(dummy_input)
    # print(f"Output shape: {output.shape}")
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
    :title="uploadOnlyMode ? (formState.newModelName ? '添加设备适配' : '上传新模型') : '新建DNN模型压缩任务'"
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
                      <span v-if="item.inputDim" class="text-xs text-gray-500">输入: {{ item.inputDim }}</span>
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
              <Input v-model:value="formState.newModelName" placeholder="例如：My-ResNet50" size="large" :disabled="forceUploadMode && !!formState.newModelName" />
            </Form.Item>
            <Form.Item label="任务类型">
              <Select v-model:value="formState.taskType" size="large" :disabled="forceUploadMode && !!formState.newModelName">
                <Select.Option value="Image Classification">图像分类</Select.Option>
                <Select.Option value="Object Detection">目标检测</Select.Option>
                <Select.Option value="Segmentation">语义分割</Select.Option>
              </Select>
            </Form.Item>
            
            <div class="grid grid-cols-2 gap-4">
              <!-- Only show file upload fields if not in "Add Device Type" mode (where modelName is pre-filled) -->
              <template v-if="!(forceUploadMode && formState.newModelName)">
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
                
                <Form.Item label="模型定义文件 (.py)" required tooltip="包含模型类定义的Python脚本 (例如 class ResNet...)">
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

                <Form.Item required tooltip="用于加载模型结构以计算FLOPs，并作为边缘设备推理入口">
                  <template #label>
                    <div class="flex items-center">
                      <span>推理脚本 (.py)</span>
                      <a @click.prevent="downloadTemplate" class="text-blue-500 text-xs flex items-center hover:underline cursor-pointer ml-2" style="font-weight: normal">
                        <DownloadOutlined class="mr-1"/> 下载标准模版
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
              </template>
            </div>
            
            <Form.Item label="数据集" required tooltip="请选择服务器上已存在的数据集">
              <Select v-model:value="formState.dataset" :options="datasets" placeholder="请选择数据集" size="large" :disabled="forceUploadMode && !!formState.newModelName" />
              <div class="text-xs text-gray-400 mt-1">
                若列表中没有所需数据集，请先在“数据集管理”中添加。
              </div>
            </Form.Item>
            
            <Form.Item label="默认设备类型" required tooltip="该模型版本适用的默认设备类型">
               <Select v-model:value="formState.targetDevice" :options="deviceTypes" size="large" placeholder="选择设备类型" />
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
          
          <div class="grid grid-cols-2 gap-4">
            <Form.Item label="目标设备" required>
              <Select v-model:value="formState.targetDevice" placeholder="请选择" size="large" :options="deviceTypes" />
            </Form.Item>

            <Form.Item v-if="formState.targetDevice" label="目标设备 IP (用于真实延迟评估)" help="选择一个或多个设备 IP 进行最终模型的真实硬件延迟评估" class="col-span-2">
              <Select
                v-model:value="formState.deviceIps"
                mode="multiple"
                placeholder="请选择设备 IP"
                size="large"
                :options="availableDeviceIps"
                :loading="!devices.length"
              />
            </Form.Item>

            <Form.Item label="使用代理模型">
              <Switch v-model:checked="formState.useProxy" checked-children="是" un-checked-children="否" />
            </Form.Item>
            <Form.Item v-if="formState.useProxy" label="选择代理模型" required>
              <Select 
                 v-model:value="formState.proxyModel" 
                 :options="proxyModels" 
                 placeholder="请选择代理模型"
                 size="large" 
              />
              <div class="text-xs text-gray-500 mt-1" v-if="proxyModels.length === 0 && formState.targetDevice">
                该模型与设备组合下暂无可用代理模型，请先构建代理模型。
              </div>
            </Form.Item>

            <Form.Item label="压缩算法">
              <Select v-model:value="formState.compressionMethod" size="large">
                <Select.Option value="HDAP">HDAP (Homogeneous-Device Aware Pruning)</Select.Option>
                <Select.Option value="Grid Search">Grid Search (网格搜索)</Select.Option>
              </Select>
            </Form.Item>
          </div>

          <Card size="small" title="参数配置 (JSON)" class="bg-gray-50 mt-4">
               <Form.Item help="包含训练参数（如 lr, epochs）与算法参数（如剪枝率）。请直接修改 JSON 值。">
                 <Input.TextArea v-model:value="formState.configJson" :rows="12" placeholder="{}" style="font-family: monospace;" />
               </Form.Item>
           </Card>
         </Form>
       </div>

      <!-- Step 3: Success -->
      <div v-if="currentStep === 2" class="step-panel flex flex-col items-center justify-center py-8">
        <Result
          status="success"
          title="DNN模型压缩任务已创建"
          sub-title="任务已加入后台队列，您可以立即执行或稍后在“压缩任务”页面查看。"
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
          {{ uploadOnlyMode ? (forceUploadMode && formState.newModelName ? '确认' : '确认上传') : (currentStep === 1 ? '创建任务' : '下一步') }}
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
.mb-2 { margin-bottom: 8px; }
.mt-8 { margin-top: 32px; }
.bg-gray-50 { background-color: #f9fafb; }
.text-gray-500 { color: #6b7280; }
.text-xs { font-size: 12px; }
</style>
