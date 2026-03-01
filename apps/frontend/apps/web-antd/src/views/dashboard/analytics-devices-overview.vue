<template>
  <Card class="overview-card">
    <div class="card-header">
      <div class="header-left">
        <div class="title">设备信息总览</div>
      </div>
    </div>

    <Row :gutter="16" class="stats-row">
      <Col class="overview-col" :xs="24" :sm="24" :md="12" :lg="12">
        <StatCard title="设备总览" variant="primary" :show-title="false">
          <template #icon>
            <DatabaseOutlined class="stat-icon primary" />
          </template>
          <InlineMetrics
            left-label="设备总数"
            :left-value="`${totalDevices}台`"
            right-label="设备类型数"
            :right-value="deviceTypes.length"
          />
          <div class="type-row">
            <div class="type-tags">
              <Tag v-for="t in topTypes" :key="t.type" color="blue">{{ t.type }} · {{ t.count }}</Tag>
              <div class="type-tags-placeholder" v-if="topTypes.length === 0">
                <span>暂无类型数据</span>
              </div>
            </div>
          </div>
        </StatCard>
      </Col>

      <Col class="overview-col" :xs="24" :sm="24" :md="12" :lg="12">
        <StatCard title="在线状态" variant="green" :show-title="false">
          <template #icon>
            <CheckCircleOutlined class="stat-icon green" />
          </template>
          <InlineMetrics
            left-label="在线设备"
            :left-value="`${onlineCount}台`"
            right-label="离线设备"
            :right-value="`${offlineCount}台`"
          />
          <div class="progress-row">
            <span class="sub-label">在线率</span>
            <Progress :percent="onlinePercent" size="small" :stroke-color="'#22c55e'" />
          </div>
        </StatCard>
      </Col>
    </Row>
  </Card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { Card, Row, Col, Progress, Tag } from "ant-design-vue";
import { DatabaseOutlined, CheckCircleOutlined } from "@ant-design/icons-vue";
import StatCard from "#/components/stat-card.vue";
import InlineMetrics from "#/components/inline-metrics.vue";

// ⭐ 必须添加样式导入，否则 Vue 无法识别 a-button / a-card
import "ant-design-vue/es/card/style";
import "ant-design-vue/es/row/style";
import "ant-design-vue/es/col/style";
import "ant-design-vue/es/progress/style";
import "ant-design-vue/es/tag/style";
import axios from "axios";

/** 设备类型结构 */
interface DeviceRow { type: string; ip: string; status: "online" | "offline" }
const devices = ref<DeviceRow[]>([]);

onMounted(async () => {
  try {
    const { data } = await axios.get("/api/devices/metrics");
    const items = data?.data?.items || data?.items || [];
    devices.value = items.map((it: any) => ({ type: it.type, ip: it.ip, status: it.status }));
  } catch (e) {
    devices.value = [];
  }
});

const totalDevices = computed(() => devices.value.length);
const onlineCount = computed(() => devices.value.filter(d => d.status === "online").length);
const offlineCount = computed(() => totalDevices.value - onlineCount.value);

const onlinePercent = computed(() => {
  const total = totalDevices.value;
  return total ? Math.round((onlineCount.value / total) * 100) : 0;
});

interface DeviceTypeItem { type: string; count: number }
const deviceTypes = computed<DeviceTypeItem[]>(() => {
  const map: Record<string, number> = {};
  devices.value.forEach((d) => { map[d.type] = (map[d.type] || 0) + 1 });
  return Object.entries(map).map(([type, count]) => ({ type, count }));
});
const topTypes = computed(() => deviceTypes.value.slice().sort((a, b) => b.count - a.count).slice(0, 3));

//
</script>

<style scoped>
.overview-card {
  border-radius: 14px !important;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 70%);
  border: 1px solid #e5e7eb;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding: 4px 2px 10px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.subtitle {
  font-size: 12px;
  color: #64748b;
}

.stats-row {
  margin-bottom: 4px;
}

.overview-col {
  display: flex;
}

.stat-box {
  border-radius: 12px;
  padding: 10px 12px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  border: 1px solid #e2e8f0;
  background: #ffffff;
  transition: all .2s;
  width: 100%;
}

.stat-box:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.stat-title {
  font-size: 15px;
  color: #334155;
}

.stat-icon {
  font-size: 18px;
}
.stat-icon.primary { color: #2563eb; }
.stat-icon.purple { color: #7c3aed; }
.stat-icon.green { color: #16a34a; }
.stat-icon.red { color: #dc2626; }

.statistic-value :deep(.ant-statistic-content) {
  font-size: 26px;
  font-weight: 700;
  color: #0f172a;
}

.sub-row {
  margin-top: 10px;
  display: grid;
  grid-template-columns: auto auto 1px auto auto;
  align-items: center;
  gap: 8px;
}
.sub-label {
  font-size: 12px;
  color: #64748b;
  white-space: nowrap;
  word-break: keep-all;
  flex-shrink: 0;
}
.sub-value {
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.sub-value.positive { color: #16a34a; }
.sub-value.negative { color: #dc2626; }
.sub-value.warning { color: #d97706; }
.sub-split {
  width: 1px;
  height: 14px;
  background: #e2e8f0;
}

.type-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.type-row {
  margin-top: 6px;
}

.type-tags-placeholder {
  margin-top: 8px;
  font-size: 12px;
  color: #94a3b8;
}

.stat-flex {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 12px;
}

.progress-row {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.progress-row :deep(.ant-progress) {
  flex: 1;
}

.ratio-text {
  font-size: 12px;
  color: #64748b;
}

.stat-primary { background: linear-gradient(180deg, #eff6ff 0%, #ffffff 80%); }
.stat-purple { background: linear-gradient(180deg, #f5f3ff 0%, #ffffff 80%); }
.stat-green { background: linear-gradient(180deg, #ecfdf5 0%, #ffffff 80%); }
.stat-red { background: linear-gradient(180deg, #fef2f2 0%, #ffffff 80%); }
.metric-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  align-items: center;
}
.metric-label {
  font-size: 13px;
  color: #475569;
}
.metric :deep(.ant-statistic-content) {
  font-size: 26px;
  font-weight: 700;
}
.inline-row {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: baseline;
}
.inline-item {
  display: flex;
  justify-content: flex-start;
  align-items: baseline;
  gap: 6px;
  white-space: nowrap;
}
.inline-item.right {
  justify-content: flex-start;
}
.inline-divider {
  color: #cbd5e1;
}
.inline-label {
  font-size: 15px;
  color: #475569;
}
.inline-value {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}
</style>
