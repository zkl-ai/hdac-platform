<script lang="ts" setup>

// import AnalyticsInferenceBoxplot from './analytics-inference.vue'
// import AnalyticsDevicesOverview from './analytics-devices-overview.vue';
import AnalyticsPipeline from './analytics-pipeline.vue';

</script>

<template>
  <div class="p-5">
    <div class="piepline">
      <AnalyticsPipeline />
    </div>
<!-- 
    <div>
      <AnalyticsInferenceBoxplot></AnalyticsInferenceBoxplot>
    </div>

    <div>
      <AnalyticsDevicesOverview></AnalyticsDevicesOverview>
    </div> -->

  </div>
</template>
<style scoped>
.piepline {
  width: 100%;
  min-height: 400px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  position: relative;
  overflow: auto;
  margin-bottom: 16px;
}
</style>
