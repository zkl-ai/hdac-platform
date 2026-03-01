<template>
  <div class="node-card">
    <!-- 顶部标题 -->
    <div class="header">
      <AppstoreOutlined class="header-icon" />
      <span class="header-text">模型库</span>
    </div>

    <!-- 图标操作区：更大的纵向卡片按钮 -->
    <div class="icon-column">
      <Tooltip placement="right" :mouse-enter-delay="0.1">
        <!-- <template #title>快速评估模型在目标设备上的性能</template> -->
        <div class="icon-btn surrogate" @click="onSurrogate">
          <div class="icon-circle">
            <DeploymentUnitOutlined />
          </div>
          <div class="icon-texts">
            <span class="icon-label">代理模型</span>
            <span class="icon-desc">快速评估模型在目标设备上的性能</span>
          </div>
          <!-- <RightOutlined class="card-arrow" /> -->
        </div>
      </Tooltip>

      <Tooltip placement="right" :mouse-enter-delay="0.1">
        <!-- <template #title>深度神经网络模型集合</template> -->
        <div class="icon-btn dnn" @click="onDnn">
          <div class="icon-circle">
            <CodeSandboxOutlined />
          </div>
          <div class="icon-texts">
            <span class="icon-label">DNN模型</span>
            <span class="icon-desc">待部署/压缩的DNN模型</span>
          </div>
          <!-- <RightOutlined class="card-arrow" /> -->
        </div>
      </Tooltip>
    </div>

    <!-- 右下角按钮 -->
    <div class="footer">
      <Button size="small" type="primary" class="open-btn" @click="onOpen" shape="round">
        <template #icon>
          <RightOutlined />
        </template>
        浏览模型库
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CodeSandboxOutlined, DeploymentUnitOutlined, RightOutlined, AppstoreOutlined } from "@ant-design/icons-vue";
import { Button, Tooltip } from 'ant-design-vue'

import { useRouter } from 'vue-router'
const router = useRouter()
const onOpen = () => router.push({ name: 'ModelLibrary' })
const onSurrogate = () => console.log("点击代理模型");
const onDnn = () => console.log("点击DNN模型");
</script>

<style scoped>
.node-card {
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #ffffff 0%, #fafafa 100%);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
  --icon-circle-size: 42px;
  --icon-font-size: 22px;
}

.header {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 12%;
}

.header-icon {
  font-size: 18px;
  color: #2563eb;
}

.header-text {
  font-size: 15px;
  font-weight: 600;
  color: #111827;
}

.icon-column {
  flex: 1;
  height: 80%;
  display: grid;
  grid-template-rows: 1fr 1fr;
  row-gap: 4%;
  margin: 8px 0;
}

.icon-btn {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: linear-gradient(180deg, #fbfbfd 0%, #f6f7fb 100%);
  border-radius: 10px;
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: background 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
  position: relative;
  overflow: hidden;
}

.icon-btn:hover {
  background: linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
  transform: translateX(2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.06);
  border-color: #d1d5db;
}

.icon-btn::before {
  content: "";
  position: absolute;
  left: -20%;
  top: -40%;
  width: 60%;
  height: 160%;
  background: radial-gradient(60% 60% at 50% 50%, rgba(37, 99, 235, 0.12) 0%, rgba(37, 99, 235, 0) 70%);
  filter: blur(6px);
  pointer-events: none;
}

.surrogate::before {
  background: radial-gradient(60% 60% at 50% 50%, rgba(37, 99, 235, 0.14) 0%, rgba(37, 99, 235, 0) 70%);
}

.dnn::before {
  background: radial-gradient(60% 60% at 50% 50%, rgba(124, 58, 237, 0.14) 0%, rgba(124, 58, 237, 0) 70%);
}

.icon-circle {
  width: var(--icon-circle-size);
  height: var(--icon-circle-size);
  background: #eef2ff;
  border: 1px solid #dbeafe;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #2563eb;
  font-size: var(--icon-font-size);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.06) inset;
}

.icon-btn:hover .icon-circle {
  transform: scale(1.06);
  box-shadow: 0 0 0 8px rgba(37, 99, 235, 0.08) inset;
}

.icon-texts {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.icon-label {
  font-size: 16px;
  color: #111827;
  font-weight: 600;
  letter-spacing: 0.2px;
}

.icon-desc {
  font-size: 12px;
  color: #6b7280;
  font-weight: 500;
}

.surrogate .icon-circle {
  background: linear-gradient(135deg, #eff6ff 0%, #e0f2fe 100%);
  border-color: #bfdbfe;
}

.dnn .icon-circle {
  background: linear-gradient(135deg, #f5f3ff 0%, #ede9fe 100%);
  border-color: #ddd6fe;
}

.surrogate .icon-circle { color: #2563eb; }
.dnn .icon-circle { color: #7c3aed; }

.card-arrow {
  margin-left: auto;
  font-size: 12px;
  color: #9ca3af;
  transition: transform 0.2s ease, color 0.2s ease;
}

.icon-btn:hover .card-arrow {
  transform: translateX(2px);
  color: #6b7280;
}

.footer {
  display: flex;
  justify-content: flex-end;
  height: 12%;
}

/* 优化“浏览模型库”按钮外观 */
:deep(.open-btn.ant-btn-primary) {
  background: linear-gradient(90deg, #2563eb 0%, #4f46e5 100%);
  border: none;
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.25);
}

.open-btn {
  font-weight: 600;
  letter-spacing: 0.2px;
}

:deep(.open-btn.ant-btn-primary:hover) {
  filter: brightness(1.06);
  transform: translateY(-1px);
}
  /* 状态样式 */
  .icon-btn.dimmed {
    opacity: 0.5;
    filter: grayscale(0.6);
  }
  
  .icon-btn.active {
    background: #eff6ff;
    border-color: #2563eb;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.15);
  }
  
  .icon-btn.active .icon-circle {
    background: #2563eb;
    color: #fff;
  }
  
  .icon-btn.active .icon-label {
    color: #1d4ed8;
  }
  
  .icon-btn.active .icon-desc {
    color: #3b82f6;
  }
</style>
