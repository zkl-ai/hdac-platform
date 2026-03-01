<template>
  <div class="inference-boxplot-wrapper">
    <div style="display: flex; gap: 12px; margin-bottom: 20px">
      <!-- 设备 -->
      <a-select
        v-model:value="selectedDevice"
        placeholder="选择设备"
        style="width: 200px"
        @change="onFilterChange"
      >
        <a-select-option v-for="d in devices" :key="d" :value="d">
          {{ d }}
        </a-select-option>
      </a-select>

      <!-- 模型 -->
      <a-select
        v-model:value="selectedModel"
        placeholder="选择模型"
        style="width: 200px"
        @change="onFilterChange"
      >
        <a-select-option v-for="m in models" :key="m" :value="m">
          {{ m }}
        </a-select-option>
      </a-select>

      <!-- 输入维度 -->
      <a-select
        v-model:value="selectedInput"
        placeholder="选择输入尺寸"
        style="width: 200px"
        @change="onFilterChange"
      >
        <a-select-option v-for="i in inputs" :key="i" :value="i">
          {{ i }}
        </a-select-option>
      </a-select>
    </div>

    <div ref="chartRef" class="boxplot-chart"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from "vue";
import axios from "axios";
import * as echarts from "echarts";
import type { ECharts, EChartsOption } from "echarts";
import { Select } from "ant-design-vue";

const ASelect = Select;
const ASelectOption = Select.Option;

/* ---------------------------------------
   类型定义
--------------------------------------- */
interface OptionsResponse {
  devices: string[];
  models: string[];
  inputs: string[];
}

interface BoxplotDataResponse {
  labels: string[];
  groups: number[][]; // ECharts boxplot 每组选 5 个数值
}

/* ---------------------------------------
   响应式变量（强类型）
--------------------------------------- */
const devices = ref<string[]>([]);
const models = ref<string[]>([]);
const inputs = ref<string[]>([]);

const selectedDevice = ref<string>();
const selectedModel = ref<string>();
const selectedInput = ref<string>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

let internalUpdate = false;
let resizeObserver: ResizeObserver | null = null;

/* ---------------------------------------
   获取 Select 选项
--------------------------------------- */
const fetchOptions = async (triggeredByUser = false) => {
  const res = await axios.get<OptionsResponse>("/api/options", {
    params: {
      device: selectedDevice.value,
      model: selectedModel.value,
      input: selectedInput.value,
    },
  });

  const data = res.data;
  internalUpdate = true;

  devices.value = data.devices;
  models.value = data.models;
  inputs.value = data.inputs;

  if (!triggeredByUser || !devices.value.includes(selectedDevice.value!)) {
    selectedDevice.value = devices.value[0];
  }
  if (!triggeredByUser || !models.value.includes(selectedModel.value!)) {
    selectedModel.value = models.value[0];
  }
  if (!triggeredByUser || !inputs.value.includes(selectedInput.value!)) {
    selectedInput.value = inputs.value[0];
  }

  internalUpdate = false;
};

/* ---------------------------------------
   获取箱型图数据
--------------------------------------- */
const fetchBoxplotData = async () => {
  if (!chart) return;

  chart.showLoading({ text: "加载中..." });
  try {
    const res = await axios.get<BoxplotDataResponse>("/api/boxplot", {
      params: {
        device: selectedDevice.value,
        model: selectedModel.value,
        input: selectedInput.value,
      },
    });

    const data = res.data;

    //

      const option: EChartsOption = {
        backgroundColor: "transparent",
        animationDuration: 600,
        animationDurationUpdate: 500,
        legend: { show: false },

      tooltip: {
        trigger: "item",
        padding: 12,
        borderRadius: 8,
        formatter: (p: any) => {
          const v = (p.data || []) as number[];
          const fmt = (n?: number) => (n == null ? "-" : Number(n).toFixed(2));
          return [
            `设备：${p.name}`,
            `最小值：${fmt(v[0])} ms`,
            `下四分位：${fmt(v[1])} ms`,
            `中位数：${fmt(v[2])} ms`,
            `上四分位：${fmt(v[3])} ms`,
            `最大值：${fmt(v[4])} ms`,
          ].join("<br/>");
        },
      },

      grid: {
        left: "5%",
        right: "5%",
        bottom: 24,
        top: 16,
        containLabel: true,
      },


      xAxis: {
        type: "category",
        name: "设备",
        nameLocation: "middle",
        nameGap: 30,
        nameTextStyle: { fontSize: 16, fontWeight: 700, color: "#1F2937" },
        data: data.labels,
        axisLabel: { fontSize: 14, fontWeight: 500, color: "#334155", hideOverlap: true, margin: 12 },
        axisTick: { alignWithLabel: true, length: 10, lineStyle: { color: "#64748B" } },
        axisLine: { lineStyle: { color: "#64748B", width: 1.5 } },
      },

      yAxis: {
        type: "value",
        name: "推理延迟 (ms)",
        nameLocation: "middle",
        nameGap: 44,
        nameRotate: 90,
        nameTextStyle: { fontSize: 16, fontWeight: 700, color: "#1F2937" },
        axisLabel: { fontSize: 14, fontWeight: 500, color: "#334155", margin: 12 },
        axisLine: { show: true, lineStyle: { color: "#64748B", width: 1.5 } },
        splitLine: { show: true, lineStyle: { type: "dashed", color: "#CBD5E1", width: 1 } },
        splitArea: { show: true, areaStyle: { color: ["rgba(148,163,184,0.06)", "rgba(148,163,184,0)"] } },
        minorTick: { show: true },
        minorSplitLine: { show: true, lineStyle: { color: "rgba(203,213,225,0.35)" } },
      },

      series: [
        {
          name: "延迟分布",
          type: "boxplot",
          data: data.groups,
        itemStyle: {
            color: new (echarts as any).graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: "#5B8FF9" },
              { offset: 1, color: "#3D76DD" },
            ]),
            borderColor: "#3D76DD",
            borderWidth: 2,
            shadowBlur: 6,
            shadowColor: "rgba(61,118,221,0.25)",
          },
          emphasis: {
            itemStyle: {
              borderWidth: 2,
            },
          },
          boxWidth: [14, 48],
        },
      ],
    };

    chart.setOption(option);
  } finally {
    chart.hideLoading();
  }
};

/* ---------------------------------------
   用户 change 操作
--------------------------------------- */
const onFilterChange = async () => {
  if (internalUpdate) return;
  await fetchOptions(true);
  await fetchBoxplotData();
};

/* ---------------------------------------
   初始化
--------------------------------------- */
onMounted(async () => {
  if (!chartRef.value) return;

  chart = echarts.init(chartRef.value);

  // 自动随容器大小变化
  resizeObserver = new ResizeObserver(() => {
    chart?.resize();
  });
  resizeObserver.observe(chartRef.value);

  await fetchOptions(false);
  await fetchBoxplotData();
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
});
</script>

<style scoped>
  .boxplot-chart {
    width: 100%;
    height: 36vh;
    min-height: 240px;
  }

.inference-boxplot-wrapper {
  width: 100%;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 60%);
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}
</style>
