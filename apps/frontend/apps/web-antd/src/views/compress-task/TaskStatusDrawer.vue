<script lang="ts" setup>
import { ref, watch, computed, onUnmounted, nextTick } from 'vue';
import { Drawer, Descriptions, Tag, Card, Button, Modal, Collapse, Select, Empty, Row, Col } from 'ant-design-vue';
import { LoadingOutlined, ReloadOutlined, CaretRightOutlined } from '@ant-design/icons-vue';
import * as echarts from 'echarts';

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

// State
const loading = ref(false);
const logsLoading = ref(false);
const detail = ref<any>(null);
const logs = ref('');
const metrics = ref<any[]>([]);
const activeKey = ref(['charts']); // Default expand charts
const logActiveKey = ref([]); // Default collapse logs

let timer: any = null;
let chart1: any = null;
let chart2: any = null;
let chart3: any = null;

const chart1Ref = ref();
const chart2Ref = ref();
const chart3Ref = ref();

const iterations = computed(() => {
    const set = new Set<number>();
    metrics.value.forEach(m => {
        if (m.iteration) set.add(Number(m.iteration));
    });
    return Array.from(set).sort((a, b) => b - a); // Descending
});

const selectedIteration = ref<number | null>(null);

const fetchData = async () => {
    if (!props.taskId) return;
    logsLoading.value = true;
    try {
        // Fetch Logs
        const resLogs = await fetch(`/api/compress/tasks/${props.taskId}/logs`);
        const jsonLogs = await resLogs.json();
        logs.value = (jsonLogs.data && jsonLogs.data.logs) ? jsonLogs.data.logs : 'No logs available.';

        // Fetch Metrics
        const resMetrics = await fetch(`/api/compress/tasks/${props.taskId}/metrics`);
        const jsonMetrics = await resMetrics.json();
        metrics.value = Array.isArray(jsonMetrics.data) ? jsonMetrics.data : [];
        
        // Auto select latest iteration if not selected
        if (selectedIteration.value === null && iterations.value.length > 0) {
            selectedIteration.value = iterations.value[0];
        }
        
        nextTick(() => {
            initECharts();
        });

    } catch (e) {
        console.error(e);
        logs.value = 'Failed to fetch data.';
    } finally {
        logsLoading.value = false;
    }
};

const updateCharts = () => {
    if (!metrics.value.length) return;
    
    // 1. Overall Pruning Process (Iteration vs Latency/FLOPs/Accuracy)
    // Filter phase='pruning_iter'
    const pruningData = metrics.value.filter(m => m.phase === 'pruning_iter').sort((a, b) => a.step - b.step);
    if (chart1 && pruningData.length > 0) {
        const x = pruningData.map(d => `Iter ${d.step}`);
        const yLat = pruningData.map(d => d.latency ? d.latency.toFixed(2) : 0);
        const yAcc = pruningData.map(d => d.accuracy ? d.accuracy.toFixed(2) : 0);

        chart1.setOption({
            title: { 
                text: '剪枝迭代过程 (Iterative Pruning)', 
                left: 'center', 
                textStyle: { fontSize: 14, fontWeight: 600, color: '#333' } 
            },
            grid: { left: '3%', right: '3%', bottom: '10%', containLabel: true },
            tooltip: { 
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#f0f0f0',
                borderWidth: 1,
                textStyle: { color: '#333' },
                axisPointer: { type: 'cross', label: { backgroundColor: '#6a7985' } }
            },
            legend: { data: ['Latency (ms)', 'Accuracy (%)'], bottom: 0, icon: 'circle' },
            xAxis: { 
                type: 'category', 
                data: x,
                axisLine: { lineStyle: { color: '#d9d9d9' } },
                axisLabel: { color: '#666' }
            },
            yAxis: [
                { 
                    type: 'value', 
                    name: 'Lat (ms)', 
                    scale: true,
                    axisLine: { show: false },
                    axisTick: { show: false },
                    splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } },
                    axisLabel: { color: '#666' }
                },
                { 
                    type: 'value', 
                    name: 'Accuracy (%)', 
                    scale: true,
                    axisLine: { show: false },
                    axisTick: { show: false },
                    splitLine: { show: false },
                    axisLabel: { color: '#666' }
                }
            ],
            series: [
                { 
                    name: 'Latency (ms)', 
                    type: 'line', 
                    data: yLat, 
                    yAxisIndex: 0, 
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    itemStyle: { color: '#faad14', borderWidth: 2, borderColor: '#fff' },
                    lineStyle: { width: 3, shadowColor: 'rgba(250, 173, 20, 0.3)', shadowBlur: 10 }
                },
                {
                    name: 'Accuracy (%)',
                    type: 'line',
                    data: yAcc,
                    yAxisIndex: 1, 
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    itemStyle: { color: '#52c41a', borderWidth: 2, borderColor: '#fff' },
                    lineStyle: { width: 3, type: 'dashed' }
                }
            ]
        });
    }

    // Filter data for selected iteration
    const iter = selectedIteration.value;
    if (!iter) return;

    // 2. Search Phase (Generation vs FLOPs/Latency)
    const searchData = metrics.value.filter(m => m.phase === 'search' && m.iteration == iter).sort((a, b) => a.step - b.step);
    if (chart2) {
        const x = searchData.map(d => d.step);
        // Use best_flops and best_latency if available, fallback to score (which is meaningless for this chart)
        const yFlops = searchData.map(d => d.best_flops ? (d.best_flops/1e6).toFixed(1) : 0);
        const yLat = searchData.map(d => d.best_latency ? d.best_latency.toFixed(2) : 0);
        
        chart2.setOption({
            title: { 
                text: `搜索过程 (Iter ${iter})`, 
                left: 'center', 
                textStyle: { fontSize: 14, fontWeight: 600, color: '#333' }
            },
            grid: { left: '3%', right: '5%', bottom: '10%', containLabel: true },
            tooltip: { 
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#f0f0f0',
                axisPointer: { type: 'cross' }
            },
            legend: { data: ['FLOPs (M)', 'Latency (ms)'], bottom: 0, icon: 'roundRect' },
            xAxis: { 
                type: 'category', 
                data: x, 
                name: 'Gen',
                axisLine: { lineStyle: { color: '#d9d9d9' } }
            },
            yAxis: [
                { 
                    type: 'value', 
                    name: 'FLOPs', 
                    scale: true,
                    splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } }
                },
                { 
                    type: 'value', 
                    name: 'Lat (ms)', 
                    scale: true, 
                    splitLine: { show: false }
                }
            ],
            series: [
                { 
                    name: 'FLOPs (M)', 
                    type: 'line', 
                    data: yFlops, 
                    yAxisIndex: 0, 
                    smooth: true,
                    showSymbol: false,
                    itemStyle: { color: '#1890ff' },
                    lineStyle: { width: 2 },
                    areaStyle: { opacity: 0.1, color: '#1890ff' }
                },
                { 
                    name: 'Latency (ms)', 
                    type: 'line', 
                    data: yLat, 
                    yAxisIndex: 1, 
                    smooth: true,
                    showSymbol: false,
                    itemStyle: { color: '#faad14' },
                    lineStyle: { width: 2, type: 'dashed' }
                }
            ]
        });
    }

    // 3. Finetune Phase (Epoch vs Loss/Acc)
    const ftData = metrics.value.filter(m => m.phase === 'finetune' && m.iteration == iter).sort((a, b) => a.step - b.step);
    if (chart3) {
        const x = ftData.map(d => d.step);
        const yLoss = ftData.map(d => d.loss?.toFixed(4));
        const yAcc = ftData.map(d => d.accuracy?.toFixed(2));
        
        chart3.setOption({
            title: { 
                text: `微调过程 (Iter ${iter})`, 
                left: 'center', 
                textStyle: { fontSize: 14, fontWeight: 600, color: '#333' }
            },
            grid: { left: '3%', right: '5%', bottom: '10%', containLabel: true },
            tooltip: { 
                trigger: 'axis',
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#f0f0f0',
                axisPointer: { type: 'cross' }
            },
            legend: { data: ['Loss', 'Accuracy (%)'], bottom: 0, icon: 'roundRect' },
            xAxis: { 
                type: 'category', 
                data: x, 
                name: 'Epoch',
                axisLine: { lineStyle: { color: '#d9d9d9' } }
            },
            yAxis: [
                { 
                    type: 'value', 
                    name: 'Loss', 
                    scale: true,
                    splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } }
                },
                { 
                    type: 'value', 
                    name: 'Acc %', 
                    scale: true,
                    splitLine: { show: false }
                }
            ],
            series: [
                { 
                    name: 'Loss', 
                    type: 'line', 
                    data: yLoss, 
                    yAxisIndex: 0, 
                    smooth: true,
                    symbol: 'emptyCircle',
                    symbolSize: 6,
                    itemStyle: { color: '#ff4d4f' },
                    lineStyle: { width: 2 },
                    areaStyle: {
                        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                            { offset: 0, color: 'rgba(255, 77, 79, 0.3)' },
                            { offset: 1, color: 'rgba(255, 77, 79, 0.05)' }
                        ])
                    }
                },
                { 
                    name: 'Accuracy (%)', 
                    type: 'line', 
                    data: yAcc, 
                    yAxisIndex: 1, 
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    itemStyle: { color: '#52c41a' },
                    lineStyle: { width: 3, shadowColor: 'rgba(82, 196, 26, 0.3)', shadowBlur: 5 }
                }
            ]
        });
    }
};

const initECharts = () => {
    if (chart1Ref.value && !chart1) chart1 = echarts.init(chart1Ref.value);
    if (chart2Ref.value && !chart2) chart2 = echarts.init(chart2Ref.value);
    if (chart3Ref.value && !chart3) chart3 = echarts.init(chart3Ref.value);
    updateCharts();
};

watch(() => selectedIteration.value, () => {
    updateCharts();
});

watch(() => props.open, (val) => {
    if (val) {
        nextTick(() => {
            // Dispose existing charts to ensure we attach to new DOM
            if (chart1) { chart1.dispose(); chart1 = null; }
            if (chart2) { chart2.dispose(); chart2 = null; }
            if (chart3) { chart3.dispose(); chart3 = null; }

            initECharts();
            // If we have taskId but no data, fetch
            if (props.taskId && metrics.value.length === 0) {
                fetchData();
            } else if (metrics.value.length > 0) {
                // If we have data, just resize/update
                updateCharts();
            }
        });
    } else {
        if (chart1) { chart1.dispose(); chart1 = null; }
        if (chart2) { chart2.dispose(); chart2 = null; }
        if (chart3) { chart3.dispose(); chart3 = null; }
    }
});

watch(() => props.taskId, async (newId) => {
  if (newId) {
    loading.value = true;
    detail.value = props.taskData || { id: newId, name: 'Task #' + newId, status: 'running', stages: [] };
    loading.value = false;
    
    // Reset charts
    metrics.value = [];
    selectedIteration.value = null;
    
    fetchData();
    
    if (timer) clearInterval(timer);
    if (detail.value.status === 'running') {
        timer = setInterval(() => {
            fetchData();
        }, 5000);
    }
    
    nextTick(() => {
        initECharts();
    });
  } else {
    detail.value = null;
    logs.value = '';
    if (timer) clearInterval(timer);
  }
}, { immediate: true });

onUnmounted(() => {
    if (timer) clearInterval(timer);
    if (chart1) chart1.dispose();
    if (chart2) chart2.dispose();
    if (chart3) chart3.dispose();
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
  if (record.compressionAlgo) p.compressionAlgo = record.compressionAlgo;
  if (record.evalMetric) p.evalMetric = record.evalMetric;
  if (record.latencyBudget !== undefined && record.latencyBudget !== null) p.latencyBudget = record.latencyBudget;
  if (record.accuracyLossLimit !== undefined && record.accuracyLossLimit !== null) p.accuracyLossLimit = record.accuracyLossLimit;
  
  if (record.algoParams) {
    try {
      const parsed = JSON.parse(record.algoParams);
      p.algoParams = parsed;
    } catch {
      p.algoParams = record.algoParams;
    }
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
    
    <div v-if="loading || !detail" class="flex justify-center items-center h-full">
        <LoadingOutlined style="font-size: 24px" />
    </div>
    
    <div v-else class="space-y-6">
      <!-- 1. Header Info -->
      <Descriptions bordered size="small" :column="2">
        <Descriptions.Item label="任务名称">{{ detail.name }}</Descriptions.Item>
        <Descriptions.Item label="当前状态">
            <Tag :color="getStatusColor(detail.status)">{{ detail.status.toUpperCase() }}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="模型">{{ detail.modelName }}</Descriptions.Item>
        <Descriptions.Item label="设备">{{ detail.deviceType }}</Descriptions.Item>
      </Descriptions>

      <!-- 2. Visualization Charts -->
      <Card title="可视化监控 (Visualization)" size="small">
         
         <div v-if="metrics.length === 0" class="py-8">
            <Empty description="暂无监控数据" />
         </div>
         <div v-else class="space-y-4">
            <!-- Overall -->
            <div ref="chart1Ref" style="height: 300px; width: 100%"></div>
            
            <!-- Iteration Selector -->
            <div class="flex items-center justify-end gap-2 border-t border-dashed pt-4 border-gray-200">
                <span class="text-gray-500">选择迭代轮次:</span>
                <Select v-model:value="selectedIteration" style="width: 120px" size="small" placeholder="Iteration">
                    <Select.Option v-for="i in iterations" :key="i" :value="i">Iter {{ i }}</Select.Option>
                </Select>
            </div>

            <Row :gutter="16">
                <Col :span="12">
                    <div ref="chart2Ref" style="height: 300px; width: 100%"></div>
                </Col>
                <Col :span="12">
                    <div ref="chart3Ref" style="height: 300px; width: 100%"></div>
                </Col>
            </Row>
         </div>
      </Card>

      <!-- 3. Logs (Collapsible) -->
      <Collapse v-model:activeKey="logActiveKey" :bordered="false">
        <Collapse.Panel key="logs" header="运行日志 (Execution Logs)">
            <template #extra>
                <Button type="link" size="small" @click.stop="fetchData">
                    <ReloadOutlined :spin="logsLoading" /> 刷新
                </Button>
            </template>
            <div class="log-container">
                <pre>{{ logs }}</pre>
            </div>
        </Collapse.Panel>
      </Collapse>
    </div>

    <Modal v-model:open="paramsModalVisible" title="任务参数详情" :footer="null" width="600px">
      <pre style="background:#f4f4f5;padding:12px;border-radius:6px;overflow:auto;max-height:500px">{{ paramsModalContent }}</pre>
    </Modal>
  </Drawer>
</template>

<style scoped>
.space-y-6 > * + * {
  margin-top: 24px;
}
.space-y-4 > * + * {
  margin-top: 16px;
}
.log-container {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12px;
    border-radius: 4px;
    height: 400px;
    overflow-y: auto;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 12px;
}
pre {
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
</style>
