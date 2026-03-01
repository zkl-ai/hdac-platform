<script lang="ts" setup>
import { ref, watch, computed, onUnmounted, nextTick } from 'vue';
import { Drawer, Descriptions, Tag, Card, Row, Col, Modal, Button, Steps, message, Alert, Select } from 'ant-design-vue';
import { LoadingOutlined, ThunderboltOutlined, ApiOutlined } from '@ant-design/icons-vue';
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
const progressChartRef = ref<EchartsUIType>();
const { renderEcharts: renderProgressChart, resize: resizeProgress } = useEcharts(progressChartRef);

const latencyChartRef = ref<EchartsUIType>();
const { renderEcharts: renderLatencyChart, resize: resizeLatency } = useEcharts(latencyChartRef);

const throughputChartRef = ref<EchartsUIType>();
const { renderEcharts: renderThroughputChart, resize: resizeThroughput } = useEcharts(throughputChartRef);

const resourceChartRef = ref<EchartsUIType>();
const { renderEcharts: renderResourceChart, resize: resizeResource } = useEcharts(resourceChartRef);

// State
const loading = ref(false);
const detail = ref<any>(null);
const devices = ref<string[]>([]);
const selectedDevice = ref<string | undefined>(undefined);
const sendingRequest = ref(false);
let timer: any = null;

const currentStep = computed(() => {
    if (!detail.value) return 0;
    const s = detail.value.status;
    if (s === 'pending') return 0;
    if (s === 'running') return 1; 
    if (s === 'succeeded') return 2; 
    if (s === 'failed') return 1;
    return 0;
});

const stepItems = computed(() => {
    const ratio = detail.value?.grayRatio || detail.value?.stages?.[0]?.grayRatio || 0;
    return [
        { title: '任务启动' },
        { title: `灰度验证 (流量: ${ratio}%)`, description: '监控评估中' },
        { title: '全量发布', description: '验证通过后自动全量' }
    ];
});

const onPromote = async () => {
    if (!detail.value) return;
    try {
        const res = await fetch(`/api/deploy/tasks/${detail.value.id}/promote`, { method: 'POST' });
        const json = await res.json();
        if (json.code === 0) {
            message.success('已完成全量发布');
            loadData(detail.value.id);
        } else {
            message.error(json.message || '操作失败');
        }
    } catch {
        message.error('网络错误');
    }
}

const onRollback = async () => {
    if (!detail.value) return;
    Modal.confirm({
        title: '确认回滚？',
        content: '回滚操作将停止当前灰度任务并标记为失败，流量将全部切回基准版本。',
        onOk: async () => {
            try {
                const res = await fetch(`/api/deploy/tasks/${detail.value.id}/rollback`, { method: 'POST' });
                const json = await res.json();
                if (json.code === 0) {
                    message.success('已回滚任务');
                    loadData(detail.value.id);
                } else {
                    message.error(json.message || '操作失败');
                }
            } catch {
                message.error('网络错误');
            }
        }
    });
}

const lastDataTime = ref('');

const updateCharts = async () => {
  if (!detail.value) return;

  try {
      const url = selectedDevice.value 
        ? `/api/deploy/tasks/${detail.value.id}/metrics?deviceId=${selectedDevice.value}`
        : `/api/deploy/tasks/${detail.value.id}/metrics`;
        
      const res = await fetch(url);
      const json = await res.json();
      const data = json.data;

      if (!data) return;
      
      // Update devices list if returned
      if (data.devices && Array.isArray(data.devices)) {
          devices.value = data.devices;
      }
      
      // Optimization: Check if data updated
      const currentLastTime = data.times?.[data.times.length - 1];
      if (currentLastTime && currentLastTime === lastDataTime.value) {
          // Data hasn't changed, skip render
          return;
      }
      if (currentLastTime) {
          lastDataTime.value = currentLastTime;
      }

      // 1. Traffic Routing Chart
      renderProgressChart({
        title: { text: '流量路由监控 (Traffic Routing)', left: 'center', textStyle: { fontSize: 14 } },
        tooltip: { trigger: 'axis' },
        legend: { data: ['Target Ratio (Config)', 'Real-time Ratio (Actual)'], top: 30 },
        xAxis: { type: 'category', data: data.times },
        yAxis: { type: 'value', name: 'Gray Traffic %', min: 0, max: 100 },
        series: [
          {
            name: 'Target Ratio (Config)',
            type: 'line',
            data: data.times.map(() => data.target_ratio || 0),
            showSymbol: false,
            lineStyle: { type: 'dashed', color: '#999' },
            itemStyle: { color: '#999' }
          },
          {
            name: 'Real-time Ratio (Actual)',
            type: 'line',
            data: data.ratio,
            areaStyle: { opacity: 0.2 },
            smooth: true,
            itemStyle: { color: '#1890ff' }
          }
        ],
        grid: { left: '5%', right: '5%', bottom: 20, top: 70, containLabel: true }
      });

      // 2. Latency Chart (ms)
      renderLatencyChart({
          title: { text: '推理延迟 (Latency)', left: 'center', textStyle: { fontSize: 14 } },
          tooltip: { trigger: 'axis' },
          xAxis: { type: 'category', data: data.times },
          yAxis: { type: 'value', name: 'ms', scale: true },
          series: [{
              name: 'Latency',
              type: 'line',
              data: data.latency,
              smooth: true,
              itemStyle: { color: '#faad14' }
          }],
          grid: { left: '5%', right: '5%', bottom: 20, top: 50, containLabel: true }
      });

      // 3. Throughput Chart (Req/s approx)
      renderThroughputChart({
          title: { text: '吞吐量 (Throughput)', left: 'center', textStyle: { fontSize: 14 } },
          tooltip: { trigger: 'axis' },
          xAxis: { type: 'category', data: data.times },
          yAxis: { type: 'value', name: 'Req/10s', scale: true },
          series: [{
              name: 'Throughput',
              type: 'line',
              data: data.throughput,
              smooth: true,
              itemStyle: { color: '#52c41a' }
          }],
          grid: { left: '5%', right: '5%', bottom: 20, top: 50, containLabel: true }
      });

      // 4. Resource Chart (CPU/Mem/GPU %)
      const series = [
          {
              name: 'CPU',
              type: 'line',
              data: data.cpu || [],
              smooth: true,
              itemStyle: { color: '#1890ff' }
          },
          {
              name: 'Memory',
              type: 'line',
              data: data.memory || [],
              smooth: true,
              itemStyle: { color: '#722ed1' }
          },
          {
              name: 'GPU',
              type: 'line',
              data: data.gpu || [],
              smooth: true,
              itemStyle: { color: '#52c41a' }
          }
      ];
      
      renderResourceChart({
          title: { text: '资源占用 (Resource)', left: 'center', textStyle: { fontSize: 14 } },
          tooltip: { trigger: 'axis' },
          legend: { data: ['CPU', 'Memory', 'GPU'], top: 30 },
          xAxis: { type: 'category', data: data.sys_times || data.times },
          yAxis: { type: 'value', name: '%', min: 0, max: 100 },
          series: series,
          grid: { left: '5%', right: '5%', bottom: 20, top: 70, containLabel: true }
      });

  } catch (e) {
      console.error(e);
  }
};

const loadData = async (id: number) => {
    loading.value = true;
    try {
        // Reset state
        lastDataTime.value = '';
        
        // Fetch fresh task details to get status
        // Since list page passes data, we might want to refresh it or just use passed data + status polling
        // For now, assume detail is populated from props or list refresh
        detail.value = props.taskData || { id: id, name: 'Task #' + id, status: 'running' };
        
        // Ensure DOM is ready before rendering charts
        nextTick(() => {
            updateCharts();
        });
        
        // Start polling if running
        if (timer) clearInterval(timer);
        if (detail.value?.status === 'running') {
            timer = setInterval(() => {
                updateCharts();
            }, 5000);
        }
    } finally {
        loading.value = false;
    }
}

const onSendTestRequest = async () => {
    // Removed: Debug logic should not be in production page
}

// Watch for Drawer Open State
watch(() => props.open, (isOpen) => {
    if (isOpen) {
        if (props.taskId) {
            loadData(props.taskId);
        }
        // Resize charts when drawer opens to ensure correct dimensions
        nextTick(() => {
            resizeProgress();
            resizeLatency();
            resizeThroughput();
            resizeResource();
        });
    } else {
        if (timer) clearInterval(timer);
    }
});

// Watch for Task ID changes while open (edge case)
watch(() => props.taskId, (newId) => {
    if (props.open && newId) {
        loadData(newId);
    }
});

onUnmounted(() => {
    if (timer) clearInterval(timer);
});

const getStatusColor = (status: string) => {
  switch (status) {
    case 'succeeded': return 'success';
    case 'running': return 'processing';
    case 'failed': return 'error';
    default: return 'default';
  }
};

// Params Modal Logic
const paramsModalVisible = ref(false);
const paramsModalContent = ref('');

const showParams = () => {
  const record = detail.value;
  if (!record) return;

  const p: any = {};
  if (record.modelName || record.candidateModel) p.modelName = record.modelName || record.candidateModel;
  if (record.grayRatio) p.grayRatio = record.grayRatio;
  if (record.evalWindowType) p.evalWindowType = record.evalWindowType;
  if (record.evalWindowValue) p.evalWindowValue = record.evalWindowValue;
  if (record.deviceSubset) p.deviceSubset = record.deviceSubset;
  if (record.deviceType) p.deviceType = record.deviceType;
  
  // Also show stages
  if (record.stages) p.stages = record.stages;

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
    
    <div v-if="loading" class="absolute inset-0 z-50 flex justify-center items-center bg-white/80">
        <LoadingOutlined style="font-size: 24px" />
    </div>
    
    <div v-show="detail" class="space-y-6">
      <!-- 0. Pipeline Status -->
      <div class="px-4 pt-2">
        <Steps :current="currentStep" :items="stepItems" size="small" :status="detail?.status === 'failed' ? 'error' : 'process'" />
      </div>

      <!-- 1. Header Info -->
      <Descriptions bordered size="small" :column="2" v-if="detail">
        <template #extra>
            <div class="flex gap-2" v-if="detail.status === 'running'">
                <Button type="primary" size="small" @click="onPromote">全量发布 (Promote)</Button>
                <Button danger size="small" @click="onRollback">回滚 (Rollback)</Button>
            </div>
        </template>
        <Descriptions.Item label="任务名称">{{ detail.name }}</Descriptions.Item>
        <Descriptions.Item label="当前状态">
            <Tag :color="getStatusColor(detail.status)">{{ detail.status?.toUpperCase() || 'UNKNOWN' }}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="选择模型">{{ detail.modelName || detail.candidateModel }}</Descriptions.Item>
        <Descriptions.Item label="设备类型">{{ detail.deviceType }}</Descriptions.Item>
        <Descriptions.Item label="灰度比例">{{ detail.grayRatio || detail.stages?.[0]?.grayRatio }}%</Descriptions.Item>
        <Descriptions.Item label="灰度设备">{{ detail.deviceSubset || '-' }}</Descriptions.Item>
      </Descriptions>
      
      <!-- 1.5 Access Info -->
      <Alert message="服务访问信息" type="info" show-icon>
        <template #description>
            <div class="flex flex-col gap-2">
                <div>
                    <span class="font-bold">API Endpoint:</span> 
                    <code class="ml-2 bg-gray-100 px-1 py-0.5 rounded">POST /api/deploy/tasks/{{ detail.id }}/inference</code>
                </div>
                <div>
                    <span class="font-bold">流量策略:</span> 
                    按比例随机路由 (当前: {{ detail.grayRatio || detail.stages?.[0]?.grayRatio }}%)
                </div>
            </div>
        </template>
      </Alert>

      <!-- 2. Traffic Chart -->
      <Card title="流量路由监控 (Traffic Routing)" size="small">
        <div style="height: 320px; width: 100%">
            <EchartsUI ref="progressChartRef" />
        </div>
      </Card>

      <!-- 3. Metrics Grid -->
      <Card title="在线性能监控 (Real-time Metrics)" size="small">
        <template #extra>
             <Select 
                v-model:value="selectedDevice" 
                style="width: 200px" 
                placeholder="选择设备 (全部)" 
                allowClear
                size="small"
                @change="updateCharts"
            >
                <Select.Option v-for="d in devices" :key="d" :value="d">{{ d }}</Select.Option>
            </Select>
        </template>
        <Row :gutter="[16, 16]">
            <Col :span="8">
                <div class="chart-container">
                    <EchartsUI ref="latencyChartRef" />
                </div>
            </Col>
            <Col :span="8">
                <div class="chart-container">
                    <EchartsUI ref="throughputChartRef" />
                </div>
            </Col>
            <Col :span="8">
                <div class="chart-container">
                    <EchartsUI ref="resourceChartRef" />
                </div>
            </Col>
        </Row>
      </Card>
    </div>

    <Modal v-model:open="paramsModalVisible" title="任务参数详情" :footer="null" width="600px">
      <pre style="background:#f4f4f5;padding:12px;border-radius:6px;overflow:auto;max-height:500px">{{ paramsModalContent }}</pre>
    </Modal>
  </Drawer>
</template>

<style scoped>
.chart-container {
    height: 320px;
    width: 100%;
    border: 1px solid #f0f0f0;
    border-radius: 4px;
    padding: 8px;
}
</style>
