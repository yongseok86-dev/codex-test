<template>
  <div class="timeseries-view">
    <ProductTimeSeries />
    <PurchaseBubbleChart />
  </div>
</template>

<script setup lang="ts">
import ProductTimeSeries from '../components/ProductTimeSeries.vue'
import PurchaseBubbleChart from '../components/PurchaseBubbleChart.vue'
</script>

<style scoped>
.timeseries-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow: auto;
  padding: 8px;
  box-sizing: border-box;
}
</style>
