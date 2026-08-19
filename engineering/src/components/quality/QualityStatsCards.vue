<template>
  <div class="qs-row">
    <div
      v-for="stat in stats"
      :key="stat.label"
      class="qs-card"
      :class="'qs-card--' + stat.type"
    >
      <div class="qs-card__icon">
        <el-icon :size="24">
          <component :is="stat.icon" />
        </el-icon>
      </div>
      <div class="qs-card__content">
        <span class="qs-card__value">{{ stat.value }}</span>
        <span class="qs-card__label">{{ stat.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 质检统计卡片（QualityInspection 拆分子组件）
 *
 * 纯展示：渲染统计卡片行（总数/合格/不合格/合格率），
 * 图标由父组件传入组件定义（@element-plus/icons-vue）。
 */
import type { Component } from 'vue'

/** 统计卡项（与主组件 StatsCard 对齐）。 */
interface StatsCardItem {
  label: string
  value: string | number
  icon: Component
  type: string
}

defineProps<{
  /** 统计卡列表。 */
  stats: StatsCardItem[]
}>()
</script>

<style scoped>
.qs-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.qs-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: var(--radius-lg);
  background: var(--bg-0);
  border: 1px solid var(--bg-200, var(--el-border-color-light));
}

.qs-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 10px;
  flex-shrink: 0;
}

.qs-card--primary .qs-card__icon {
  background: var(--brand-50, var(--el-color-primary-light-9));
  color: var(--brand-500, var(--el-color-primary));
}

.qs-card--success .qs-card__icon {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}

.qs-card--danger .qs-card__icon {
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
}

.qs-card--warning .qs-card__icon {
  background: var(--el-color-warning-light-9);
  color: var(--el-color-warning);
}

.qs-card__content {
  display: flex;
  flex-direction: column;
}

.qs-card__value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--text-primary);
}

.qs-card__label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
</style>
