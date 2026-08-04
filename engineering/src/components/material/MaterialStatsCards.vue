<template>
  <div class="stats-row">
    <div
      v-for="stat in cards"
      :key="stat.label"
      class="stat-card"
      :class="'stat-card--' + stat.type"
    >
      <div class="stat-card__icon">
        <el-icon :size="24">
          <component :is="stat.icon" />
        </el-icon>
      </div>
      <div class="stat-card__content">
        <span class="stat-card__value">{{ stat.value }}</span>
        <span class="stat-card__label">{{ stat.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

interface StatsCard {
  label: string
  value: number
  icon: Component
  type: string
}

defineProps<{
  cards: StatsCard[]
}>()
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.stat-card__icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: var(--primary-bg, #ecf5ff);
  color: var(--el-color-primary);
  flex-shrink: 0;
}

.stat-card--warning .stat-card__icon {
  background: var(--warning-bg);
  color: var(--warning);
}

.stat-card--danger .stat-card__icon {
  background: var(--error-bg);
  color: var(--error);
}

.stat-card--info .stat-card__icon {
  background: var(--info-bg);
  color: var(--info);
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-card__value {
  font-size: 24px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary, #303133);
}

.stat-card__label {
  font-size: 13px;
  color: var(--text-secondary, #909399);
}
</style>