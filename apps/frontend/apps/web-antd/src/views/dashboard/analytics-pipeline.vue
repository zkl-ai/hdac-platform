<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import ModelLibraryNode from './pipeline-node/model-library-node.vue'
import SurrogateNode from './pipeline-node/surrogate-node.vue'
import CompressNode from './pipeline-node/compress-node.vue'
import DeployNode from './pipeline-node/deploy-node.vue'

const selectedScenario = ref<string | null>(null)
const hoveredScenario = ref<string | null>(null)

const activeScenario = computed(() => hoveredScenario.value || selectedScenario.value)

const toggleScenario = (scenario: string) => {
  // 如果点击的是同一个，取消选中；否则选中新的
  if (selectedScenario.value === scenario) {
    selectedScenario.value = null
  } else {
    selectedScenario.value = scenario
  }
}

const LEFT = reactive({ x: 72, y: 60, width: 260, height: 380 })
let GAP_X = 120
let GAP_Y = 64
const GAP_COMP = 44
const RIGHT = reactive({ x: LEFT.x + LEFT.width + GAP_X + GAP_COMP, width: 420, height: 160 })
const POS = reactive({ surrogateY: LEFT.y, compressY: LEFT.y + RIGHT.height + GAP_Y, deployY: LEFT.y + (RIGHT.height + GAP_Y) * 2 })
const centerY = (y: number) => y + RIGHT.height / 2
const ARROW_GAP_START = 34
const ARROW_GAP_END = 24
const ARROW_GAP_START_DEPLOY = 34
const ARROW_GAP_END_DEPLOY = 24
const DUP_LINE_OFFSET = 9
const leftEdgeX = computed(() => LEFT.x + LEFT.width)
const rightEdgeX = computed(() => RIGHT.x)
const midXSurrogate = computed(() => (leftEdgeX.value + ARROW_GAP_START + rightEdgeX.value - ARROW_GAP_END - 2) / 2)
const midXCompress = computed(() => (leftEdgeX.value + ARROW_GAP_START + rightEdgeX.value - ARROW_GAP_END - 2) / 2)
const midXDeploy = computed(() => (leftEdgeX.value + ARROW_GAP_START_DEPLOY + rightEdgeX.value - ARROW_GAP_END_DEPLOY - 2) / 2)
const labelDeploy = '待部署DNN模型'
const RIGHT_SHIFT = 0
const wrapperRef = ref<HTMLDivElement | null>(null)
const svgSize = ref({ width: 0, height: 0 })
const contentHeight = ref(600)
const resize = () => {
  const el = wrapperRef.value
  if (!el) return
  const width = el.clientWidth
  const baseHeight = Math.max(el.clientHeight, 520, Math.round(width * 0.45))
  LEFT.width = Math.round(Math.max(220, Math.min(300, width * 0.23)))
  LEFT.height = Math.max(380, baseHeight - LEFT.y * 2)
  GAP_X = Math.round(Math.max(48, Math.min(88, width * 0.03)))
  const feedbackReserve = 0
  const marginRight = 24
  const minRightWidth = 380
  const availableRightWidth = width - (LEFT.x + LEFT.width + GAP_X + GAP_COMP) - feedbackReserve - marginRight
  const maxRightWidth = Math.min(availableRightWidth, Math.round(width * 0.54))
  RIGHT.width = Math.round(Math.max(minRightWidth, maxRightWidth))
  RIGHT.x = width - marginRight - feedbackReserve - RIGHT.width - RIGHT_SHIFT
  GAP_Y = Math.round(Math.max(48, Math.min(80, baseHeight * 0.06)))
  RIGHT.height = Math.floor((LEFT.height - GAP_Y * 2) / 3)
  POS.surrogateY = LEFT.y
  POS.compressY = POS.surrogateY + RIGHT.height + GAP_Y
  POS.deployY = POS.compressY + RIGHT.height + GAP_Y
  contentHeight.value = POS.deployY + RIGHT.height + LEFT.y
  svgSize.value = { width, height: contentHeight.value }
}
onMounted(() => {
  resize()
  window.addEventListener('resize', resize)
})
</script>

<template>
  <div class="flowchart-wrapper" :style="{ height: `${contentHeight}px` }" ref="wrapperRef" @click="selectedScenario = null">
    <svg class="edges-layer" :width="svgSize.width" :height="svgSize.height">
      <defs>
        <filter id="edgeShadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#1f2937" flood-opacity="0.15"/>
        </filter>
        <marker id="arrow-ml" markerWidth="12" markerHeight="12" refX="8" refY="6" orient="auto-start-reverse">
          <path d="M2,2 L10,6 L2,10 C1,9 1,3 2,2 Z" fill="#2563eb" stroke="#1d4ed8" stroke-width="0.6" />
        </marker>
      </defs>
      <g filter="url(#edgeShadow)">
        <!-- 代理模型：上行（模型查询，左 -> 右） -->
        <line :x1="leftEdgeX + ARROW_GAP_START" :y1="centerY(POS.surrogateY) - DUP_LINE_OFFSET" :x2="rightEdgeX - ARROW_GAP_END - 2" :y2="centerY(POS.surrogateY) - DUP_LINE_OFFSET"
              class="connection-line"
              :class="{ 'animated-line': true, 'active-line': activeScenario === 'surrogate' }"
              stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
              marker-end="url(#arrow-ml)" />
        <text :x="midXSurrogate" :y="centerY(POS.surrogateY) - DUP_LINE_OFFSET - 12" class="edge-label" text-anchor="middle"
              :class="{ 'active-label': activeScenario === 'surrogate' }">DNN模型</text>
        <!-- 代理模型：下行（评估结果，右 -> 左） -->
        <line :x1="rightEdgeX - ARROW_GAP_END - 2" :y1="centerY(POS.surrogateY) + DUP_LINE_OFFSET" :x2="leftEdgeX + ARROW_GAP_START" :y2="centerY(POS.surrogateY) + DUP_LINE_OFFSET"
              class="connection-line"
              :class="{ 'animated-line': true, 'active-line': activeScenario === 'surrogate' }"
              stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
              marker-end="url(#arrow-ml)" />
        <text :x="midXSurrogate" :y="centerY(POS.surrogateY) + DUP_LINE_OFFSET + 16" class="edge-label" text-anchor="middle"
              :class="{ 'active-label': activeScenario === 'surrogate' }">代理模型</text>
        <!-- 模型压缩：上行（模型查询，左 -> 右） -->
        <line :x1="leftEdgeX + ARROW_GAP_START" :y1="centerY(POS.compressY) - DUP_LINE_OFFSET" :x2="rightEdgeX - ARROW_GAP_END - 2" :y2="centerY(POS.compressY) - DUP_LINE_OFFSET"
              class="connection-line"
              :class="{ 'animated-line': true, 'active-line': activeScenario === 'compress' }"
              stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
              marker-end="url(#arrow-ml)" />
        <text :x="midXCompress" :y="centerY(POS.compressY) - DUP_LINE_OFFSET - 12" class="edge-label" text-anchor="middle"
              :class="{ 'active-label': activeScenario === 'compress' }">DNN模型</text>
        <!-- 模型压缩：下行（压缩结果，右 -> 左） -->
        <line :x1="rightEdgeX - ARROW_GAP_END - 2" :y1="centerY(POS.compressY) + DUP_LINE_OFFSET" :x2="leftEdgeX + ARROW_GAP_START" :y2="centerY(POS.compressY) + DUP_LINE_OFFSET"
              class="connection-line"
              :class="{ 'animated-line': true, 'active-line': activeScenario === 'compress' }"
              stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
              marker-end="url(#arrow-ml)" />
        <text :x="midXCompress" :y="centerY(POS.compressY) + DUP_LINE_OFFSET + 16" class="edge-label" text-anchor="middle"
              :class="{ 'active-label': activeScenario === 'compress' }">压缩DNN模型</text>
        <line :x1="leftEdgeX + ARROW_GAP_START_DEPLOY" :y1="centerY(POS.deployY)" :x2="rightEdgeX - ARROW_GAP_END_DEPLOY - 2" :y2="centerY(POS.deployY)"
              class="connection-line"
              :class="{ 'animated-line': true, 'active-line': activeScenario === 'deploy' }"
              stroke="#2563eb" stroke-width="2.25" stroke-linecap="round" stroke-linejoin="round"
              marker-end="url(#arrow-ml)" />
        <text :x="midXDeploy" :y="centerY(POS.deployY) - 12" class="edge-label" text-anchor="middle"
              :class="{ 'active-label': activeScenario === 'deploy' }">
          {{ labelDeploy }}
        </text>
      </g>
      </svg>
    
    <div class="node" :style="{ left: `${LEFT.x}px`, top: `${LEFT.y}px`, width: `${LEFT.width}px`, height: `${LEFT.height}px` }">
      <ModelLibraryNode :activeScenario="activeScenario" @select="toggleScenario" />
    </div>

    <div class="node" :style="{ left: `${RIGHT.x}px`, top: `${POS.surrogateY}px`, width: `${RIGHT.width}px`, height: `${RIGHT.height}px` }"
         @mouseenter="hoveredScenario = 'surrogate'" @mouseleave="hoveredScenario = null">
      <SurrogateNode :activeScenario="activeScenario" @select="toggleScenario" />
    </div>

    <div class="node" :style="{ left: `${RIGHT.x}px`, top: `${POS.compressY}px`, width: `${RIGHT.width}px`, height: `${RIGHT.height}px` }"
         @mouseenter="hoveredScenario = 'compress'" @mouseleave="hoveredScenario = null">
      <CompressNode :activeScenario="activeScenario" @select="toggleScenario" />
    </div>

    <div class="node" :style="{ left: `${RIGHT.x}px`, top: `${POS.deployY}px`, width: `${RIGHT.width}px`, height: `${RIGHT.height}px` }"
         @mouseenter="hoveredScenario = 'deploy'" @mouseleave="hoveredScenario = null">
      <DeployNode :activeScenario="activeScenario" @select="toggleScenario" />
    </div>
  </div>
</template>

<style scoped>
.flowchart-wrapper {
  position: relative;
  width: 100%;
  min-height: 600px;
  background: #fff;
}

.edges-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.node {
  position: absolute;
}

/* 连线动画与样式 */
.connection-line {
  transition: all 0.3s ease;
}

.animated-line {
  stroke-dasharray: 10 5;
  animation: flow 1s linear infinite;
}

.active-line {
  stroke: #2563eb;
  stroke-width: 3;
  filter: drop-shadow(0 0 4px rgba(37, 99, 235, 0.5));
}

.edge-label {
  fill: #6b7280;
  font-size: 13px;
  pointer-events: none;
  transition: opacity 0.3s ease, transform 0.3s ease;
}
.active-label {
  fill: #1f2937;
  font-weight: 600;
}

@keyframes flow {
  from {
    stroke-dashoffset: 20;
  }
  to {
    stroke-dashoffset: 5;
  }
}

@media (min-width: 1400px) {
  .flowchart-wrapper {
    min-height: 680px;
  }
}
@media (max-width: 1200px) {
  .flowchart-wrapper {
    min-height: 640px;
  }
}

/* 放大流程图内所有文字与图标比例（仅作用于流程图范围） */
:deep(.flowchart-wrapper) {
  font-size: 15px;
}

/* 统一增大各节点标题与图标尺寸 */
:deep(.flowchart-wrapper .node-card .header-text) {
  font-size: 18px;
}
:deep(.flowchart-wrapper .node-card .header-icon) {
  font-size: 22px;
}

/* 统一增大模型库卡片内的标签与说明 */
:deep(.flowchart-wrapper .node-card .icon-label) {
  font-size: 17px;
}
:deep(.flowchart-wrapper .node-card .icon-desc) {
  font-size: 13px;
}

/* 增大按钮文字（不改变按钮布局） */
:deep(.flowchart-wrapper .node-card .open-btn),
:deep(.flowchart-wrapper .ant-btn) {
  font-size: 15px;
}

/* 提升模型库卡片图标比例（覆盖节点内部变量） */
:deep(.flowchart-wrapper .node-card) {
  --icon-circle-size: 46px;
  --icon-font-size: 24px;
}
</style>
