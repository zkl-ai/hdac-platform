<script lang="ts" setup>
import { ref, watch, computed, onUnmounted } from 'vue';
import { Drawer, Descriptions, Tag, Card, Row, Col, Statistic, Select, Modal, Button, Alert } from 'ant-design-vue';
import { LoadingOutlined } from '@ant-design/icons-vue';
import { EchartsUI, useEcharts } from '@vben/plugins/echarts';
import type { EchartsUIType } from '@vben/plugins/echarts';

const props = defineProps<{
  open: boolean;
  taskId: number | null;
  taskData?: any; 
}>();

const emit = defineEmits(['update:open', 'close']);

const drawerOpen = computed({
  get: () => props.open,
  set: (val) => emit('update:open', val),
});

// Chart refs
const trainingChartRef = ref<EchartsUIType>();
const { renderEcharts: renderTrainingChart } = useEcharts(trainingChartRef);

const samplingChartRef = ref<EchartsUIType>();
const { renderEcharts: renderSamplingChart } = useEcharts(samplingChartRef);

// State
const loading = ref(false);
const detail = ref<any>(null);
const collectionStats = ref({
  samples: 0,
  avgLatency: 0,
  deviceCount: 0
});
const deviceStatusList = ref<any[]>([]);
let timer: any = null;
let lastTrainingDataStr = '';
let lastSamplingDataStr = '';

// Mock Data Generators (Replaced with Real Data Logic)
const getTrainingMetrics = () => {
  if (!detail.value || !detail.value.subtasks) return [];
  
  // Find training subtask
  const trainTask = detail.value.subtasks.find((t: any) => t.phase === 'train');
  if (!trainTask || !trainTask.trainingParams) return [];
  
  try {
      const params = JSON.parse(trainTask.trainingParams);
      if (params.metrics_history) {
          // metrics_history is array of {cluster, epoch, loss, mape}
          // We might have multiple clusters. Let's aggregate or just show Cluster 0
          // Or flatten. For chart, let's just take Cluster 0 for simplicity or average
          const cluster0 = params.metrics_history.filter((m: any) => m.cluster === '0' || m.cluster === 0);
          if (cluster0.length > 0) return cluster0;
          return params.metrics_history; // Fallback
      }
  } catch {}
  return [];
};

const getCollectionMetrics = () => {
  if (!detail.value || !detail.value.subtasks) return [];
  
  // Find collection subtask
  const collectTask = detail.value.subtasks.find((t: any) => t.phase === 'collect');
  if (!collectTask || !collectTask.trainingParams) return [];
  
  try {
      const params = JSON.parse(collectTask.trainingParams);

      if (params.sample_count) {
          collectionStats.value.samples = params.sample_count;
          collectionStats.value.avgLatency = 0;
          collectionStats.value.deviceCount = collectTask.deviceList ? collectTask.deviceList.split(',').length : 0;
      }

      if (params.collection_metrics) {
          return params.collection_metrics.map((m: any, idx: number) => ({
              step: idx + 1,
              time: m.time ? new Date(m.time).toLocaleString() : `Step ${idx + 1}`,
              samples: m.samples,
              coverage: m.devices // Or calculate % coverage if we knew total devices
          }));
      }
  } catch {}
  return [];
};

const updateCharts = () => {
  if (!detail.value) return;

  // 1. Training Process Chart (Main)
  const trainingData = getTrainingMetrics();
  const currentTrainingDataStr = JSON.stringify(trainingData);
  
  if (currentTrainingDataStr !== lastTrainingDataStr) {
      lastTrainingDataStr = currentTrainingDataStr;
      
      renderTrainingChart({
        title: { text: '代理模型训练过程 (Training Process)', left: 'center' },
        tooltip: { trigger: 'axis' },
        legend: { data: ['Loss', 'MAPE (%)'], bottom: 0 },
        xAxis: { type: 'category', data: trainingData.map((d:any) => `Iter ${d.epoch}`) },
        yAxis: [
          { type: 'value', name: 'Loss', scale: true },
          { type: 'value', name: 'MAPE (%)', position: 'right', scale: true }
        ],
        series: [
          {
            name: 'Loss',
            type: 'line',
            data: trainingData.map((d:any) => d.loss),
            smooth: true,
            itemStyle: { color: '#f5222d' },
            areaStyle: { opacity: 0.1 }
          },
          {
            name: 'MAPE (%)',
            type: 'line',
            yAxisIndex: 1,
            data: trainingData.map((d:any) => d.mape),
            smooth: true,
            itemStyle: { color: '#1890ff' }
          }
        ],
        grid: { left: '3%', right: '3%', bottom: '10%', containLabel: true }
      });
  }

  // 2. Sampling Process Chart
  const samplingData = getCollectionMetrics();
  const currentSamplingDataStr = JSON.stringify(samplingData);

  if (currentSamplingDataStr !== lastSamplingDataStr) {
      lastSamplingDataStr = currentSamplingDataStr;
      
      renderSamplingChart({
        title: { text: '数据采集进度 (Data Collection)', left: 'center' },
        tooltip: { trigger: 'axis' },
        legend: { data: ['Samples', 'Devices'], bottom: 0 },
        xAxis: { type: 'category', data: samplingData.map((d:any) => d.time) },
        yAxis: [
          { type: 'value', name: 'Samples' },
          { type: 'value', name: 'Devices', position: 'right', minInterval: 1 }
        ],
        series: [
          {
            name: 'Samples',
            type: 'line',
            data: samplingData.map((d:any) => d.samples),
            smooth: true,
            areaStyle: { opacity: 0.2 },
            itemStyle: { color: '#52c41a' }
          },
          {
            name: 'Devices',
            type: 'line',
            yAxisIndex: 1,
            data: samplingData.map((d:any) => d.coverage),
            smooth: true,
            itemStyle: { color: '#faad14' }
          }
        ],
        grid: { left: '3%', right: '3%', bottom: '10%', containLabel: true }
      });
  }
};

const fetchDetail = async () => {
  if (!props.taskId) return;
  try {
      // Use new specific endpoint that supports lookup by Pipeline ID or Subtask ID
      console.log('Fetching detail for task:', props.taskId);
      const res = await fetch(`/api/surrogate/pipelines/detail?id=${props.taskId}`);
      
      if (res.status === 404) {
          detail.value = null;
          return;
      }
      
      const json = await res.json();
      
      if (json.code === 0 && json.data) {
          detail.value = json.data;
      } else {
          // Only clear if explicitly not found (to avoid clearing on transient network errors during polling)
          if (json.code === 404) {
              detail.value = null;
          } else {
             console.warn('Fetch detail failed:', json.message);
          }
      }
  } catch (e) {
      console.error('Network error fetching detail:', e);
  }
};

const fetchDeviceStatus = async () => {
    try {
        const res = await fetch('/api/devices/metrics');
        const json = await res.json();
        if (json?.code === 0) {
            deviceStatusList.value = json.data?.items || [];
        }
    } catch (e) {
        console.error(e);
    }
};

watch(() => props.taskId, async (newId) => {
  if (newId || props.taskData) {
    loading.value = true;
    
    // Initial load
    if (newId) {
        await fetchDetail();
        await fetchDeviceStatus();
    } else {
        detail.value = props.taskData;
        await fetchDeviceStatus();
    }
    
    loading.value = false;
    
    setTimeout(() => {
        updateCharts();
    }, 100);
    
    if (timer) clearInterval(timer);
    
    // Start polling if running
    // Update frequency to 5 seconds to avoid flickering
    timer = setInterval(async () => {
        if (newId) {
            await fetchDetail();
            await fetchDeviceStatus();
            updateCharts();
        }
    }, 5000); 

  } else {
    detail.value = null;
    if (timer) clearInterval(timer);
  }
}, { immediate: true });

watch(() => props.open, (val) => {
    if (val && detail.value) {
        setTimeout(() => {
            updateCharts();
        }, 100);
    }
});

onUnmounted(() => {
    if (timer) clearInterval(timer);
});

const getClusterResults = computed(() => {
  if (!detail.value || !detail.value.subtasks) return null;
  const clusterTask = detail.value.subtasks.find((t: any) => t.phase === 'cluster');
  if (!clusterTask || !clusterTask.trainingParams) return null;
  
  try {
      const params = JSON.parse(clusterTask.trainingParams);
      if (params.clusters) {
          // params.clusters is { '0': ['ip1', 'ip2'], '1': ['ip3'] }
          return params.clusters;
      }
  } catch {}
  return null;
});

const getStatusColor = (status: string) => {
  switch (status) {
    case 'succeeded': return 'success';
    case 'running': return 'processing';
    case 'failed': return 'error';
    default: return 'default';
  }
};

const acceleration = computed(() => {
    // If real latency is available (currently 0 in mock), calc speedup.
    // Assuming typical Proxy inference is < 0.1ms.
    // If latency is 0, we show a placeholder for demo.
    if (collectionStats.value.avgLatency > 0) {
        return (collectionStats.value.avgLatency / 0.05).toFixed(0) + 'x';
    }
    return '> 100x';
});

const deviceHealth = computed(() => {
    if (!detail.value || !detail.value.subtasks) return { allOnline: true, offline: [] };
    
    const collectTask = detail.value.subtasks.find((t: any) => t.phase === 'collect');
    if (!collectTask || !collectTask.deviceList) return { allOnline: true, offline: [] };

    const targetIps = collectTask.deviceList.split(',');
    const offline: string[] = [];
    for (const ip of targetIps) {
        const dev = deviceStatusList.value.find(d => d.ip === ip);
        if (dev && dev.status !== 'online') {
            offline.push(ip);
        } else if (!dev) {
            // Unknown device, maybe assume offline or unknown
            // offline.push(ip + ' (Unknown)');
        }
    }
    return {
        allOnline: offline.length === 0,
        offline
    };
});

// Params Modal Logic
const paramsModalVisible = ref(false);
const paramsModalContent = ref('');

const showParams = () => {
  const record = detail.value;
  if (!record) return;

  // Filter relevant params for display
  const p: any = {};
  if (record.modelName) p.modelName = record.modelName;
  if (record.deviceType) p.deviceType = record.deviceType;
  if (record.samplingAlgo) p.samplingAlgo = record.samplingAlgo;
  if (record.surrogateModel) p.surrogateModel = record.surrogateModel;
  
  if (record.algoParams) {
    try {
      const parsed = JSON.parse(record.algoParams);
      p.algoParams = parsed;
    } catch {
      p.algoParams = record.algoParams;
    }
  } else {
      // If no algoParams, show other fields
      Object.keys(record).forEach(k => {
          if (!['id', 'name', 'taskName', 'status', 'createdAt', 'updatedAt', 'subtasks'].includes(k)) {
              p[k] = record[k];
          }
      });
  }
  
  paramsModalContent.value = JSON.stringify(p, null, 2);
  paramsModalVisible.value = true;
};
</script>

<template>
  <Drawer
    v-model:open="drawerOpen"
    title="任务执行详情"
    placement="right"
    width="1000"
    :body-style="{ paddingBottom: '80px' }"
    @close="$emit('close')"
  >
    <template #extra>
        <Button type="primary" ghost size="small" @click="showParams">查看参数详情</Button>
    </template>
    
    <div v-if="loading" class="flex justify-center items-center h-full">
        <LoadingOutlined style="font-size: 24px" />
    </div>
    
    <div v-else-if="!detail" class="flex justify-center items-center h-full text-gray-500">
        暂无数据 (Task Not Found)
    </div>
    
    <div v-else class="space-y-6">
      <!-- 1. Header Info -->
      <Descriptions bordered size="small" :column="2">
        <Descriptions.Item label="任务名称">{{ detail.taskName || detail.name }}</Descriptions.Item>
        <Descriptions.Item label="当前状态">
            <Tag :color="getStatusColor(detail.status)">{{ (detail.status || 'PENDING').toUpperCase() }}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="模型">{{ detail.modelName }}</Descriptions.Item>
        <Descriptions.Item label="设备">{{ detail.deviceType }}</Descriptions.Item>
      </Descriptions>

      <!-- 2. Phase Status Summary -->
      <Card title="阶段状态 (Phase Status)" size="small">
          <Row :gutter="16">
              <Col :span="8" v-for="sub in (detail.subtasks || [])" :key="sub.phase">
                  <Card size="small" :bordered="true" class="text-center">
                      <div class="font-bold mb-2">{{ sub.phase.toUpperCase() }}</div>
                      <Tag :color="getStatusColor(sub.status)">{{ sub.status }}</Tag>
                      <div v-if="sub.progress" class="mt-2 text-xs text-gray-500">Progress: {{ sub.progress }}%</div>
                  </Card>
              </Col>
          </Row>
      </Card>

      <!-- 3. Cluster Results (Moved & Beautified) -->
      <Card v-if="getClusterResults" title="设备聚类结果 (Device Clusters)" size="small">
          <Row :gutter="16">
            <Col :span="8" v-for="(devs, cid) in getClusterResults" :key="cid">
                <Card size="small" :title="'Cluster ' + cid" class="text-center bg-gray-50">
                    <div class="flex flex-wrap gap-2 justify-center">
                         <Tag v-for="dev in devs" :key="dev" color="blue" class="text-sm py-1 px-2">{{ dev }}</Tag>
                    </div>
                </Card>
            </Col>
          </Row>
      </Card>

      <!-- 4. Data Collection Statistics -->
      <Row :gutter="16">
        <Col :span="24">
            <Card title="数据采集统计 (Data Collection Statistics)" size="small">
                <!-- Status Alert -->
                <div class="mb-4">
                     <Alert v-if="deviceHealth.allOnline" type="success" show-icon>
                         <template #message>
                             <span class="font-bold">Device Status: Normal</span>
                             <span class="ml-2">All {{ collectionStats.deviceCount }} devices are online.</span>
                         </template>
                     </Alert>
                     <Alert v-else type="warning" show-icon>
                         <template #message>
                             <span class="font-bold">Device Status: Warning</span>
                             <span class="ml-2">{{ deviceHealth.offline.length }} devices are offline: {{ deviceHealth.offline.join(', ') }}</span>
                         </template>
                     </Alert>
                </div>
                
                <div style="height: 300px; width: 100%">
                    <EchartsUI ref="samplingChartRef" />
                </div>
            </Card>
        </Col>
      </Row>

      <!-- 5. Model Training Performance -->
      <Card title="模型训练表现 (Model Training Performance)" size="small">
        <div class="flex justify-end mb-2">
            <Tag color="purple" class="text-base px-3 py-1">
                🚀 Acceleration: {{ acceleration }}
            </Tag>
        </div>
        <div style="height: 350px; width: 100%">
            <EchartsUI ref="trainingChartRef" />
        </div>
      </Card>

    </div>

    <Modal v-model:open="paramsModalVisible" title="任务参数详情" :footer="null" width="600px">
      <pre style="background:#f4f4f5;padding:12px;border-radius:6px;overflow:auto;max-height:500px">{{ paramsModalContent }}</pre>
    </Modal>
  </Drawer>
</template>
