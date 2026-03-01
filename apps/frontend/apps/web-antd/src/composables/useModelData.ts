import { ref } from 'vue'
import { message } from 'ant-design-vue'

export interface ModelOption {
  label: string
  value: string
  type: string
  dataset: string
  accuracy: string
  taskType: string
  inputDim?: string
  outputDim?: string
  key: string // unique key for selection
  modelFlops?: string | number // Model-level FLOPs
  perf?: { device: string, latency: number, flops: number }[] // Device-specific performance
}

export interface DeviceOption {
  label: string
  value: string
}

export function useModelData() {
  const existingModels = ref<ModelOption[]>([])
  const modelTree = ref<any[]>([])
  const deviceTypes = ref<DeviceOption[]>([])
  const loading = ref(false)

  const loadData = async () => {
    loading.value = true
    try {
      // Mock Models
      const res = await fetch('/api/models/tree')
      const json = await res.json()
      const items = json?.data?.items || json?.items || []
      
      modelTree.value = items

      // Flatten the tree structure to get model variants (Model -> Dataset)
      const options: ModelOption[] = []
      
      items.forEach((m: any) => {
          // Collect performance data from children (Device Groups)
          const perfData: { device: string, latency: number, flops: number }[] = []
          const datasets = new Set<string>()

          if (m.children) {
              m.children.forEach((dev: any) => {
                  // dev is Device Group
                  if (dev.children) {
                      dev.children.forEach((leaf: any) => {
                          if (leaf.dataset) datasets.add(leaf.dataset)
                          if (!leaf.compressed) { 
                              perfData.push({
                                  device: dev.deviceType,
                                  latency: leaf.avgLatencyMs,
                                  flops: leaf.flops
                              })
                          }
                      })
                  }
              })
          }

          if (datasets.size === 0) {
              options.push({
                  label: m.name,
                  value: m.name,
                  type: m.type || 'DNN',
                  dataset: '-',
                  accuracy: '-',
                  taskType: m.taskType || 'Unknown',
                  inputDim: m.inputDim,
                  outputDim: m.outputDim,
                  key: `${m.name}|-`,
                  modelFlops: m.modelFlops,
                  perf: perfData
              })
          } else {
              datasets.forEach(ds => {
                  // Find accuracy for this dataset
                  let accuracy = '-'
                  if (m.children) {
                      for (const dev of m.children) {
                          if (dev.children) {
                              const v = dev.children.find((x: any) => x.dataset === ds && x.datasetAccuracy)
                              if (v) {
                                  accuracy = v.datasetAccuracy
                                  break
                              }
                          }
                      }
                  }

                  options.push({
                      label: m.name,
                      value: m.name,
                      type: m.type || 'DNN',
                      dataset: ds,
                      accuracy: accuracy,
                      taskType: m.taskType || 'Unknown',
                      inputDim: m.inputDim,
                      outputDim: m.outputDim,
                      key: `${m.name}|${ds}`,
                      modelFlops: m.modelFlops,
                      perf: perfData
                  })
              })
          }
      })
      
      existingModels.value = options
  
      // Fetch devices from metrics API to get active devices
      const resDev = await fetch('/api/devices/metrics')
      const jsonDev = await resDev.json()
      const devItems = jsonDev?.data?.items || jsonDev?.items || []
      
      // Filter for online devices and extract unique types
      const activeTypes = new Set<string>()
      devItems.forEach((d: any) => {
          if (d.status === 'online' && d.type) {
              activeTypes.add(d.type)
          }
      })
      
      deviceTypes.value = Array.from(activeTypes).map(t => ({ label: t, value: t }))
  
    } catch (e) {
       message.error('加载模型数据失败，请检查网络')
    } finally {
      loading.value = false
    }
  }

  const formatFlops = (flops: any) => {
    if (!flops) return ''
    const num = Number(flops)
    if (isNaN(num)) return flops // Return as is if already string formatted or invalid
    
    if (num >= 1e9) {
      return (num / 1e9).toFixed(2) + ' GFLOPs'
    }
    if (num >= 1e6) {
      return (num / 1e6).toFixed(2) + ' MFLOPs'
    }
    return num + ' FLOPs'
  }

  return {
    existingModels,
    modelTree,
    deviceTypes,
    loading,
    loadData,
    formatFlops
  }
}
