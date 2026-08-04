<template>
  <div class="stats-row">
    <div
      v-for="kpi in kpiCards"
      :key="kpi.title"
      class="stat-card"
    >
      <div
        class="stat-card__icon"
        :style="{ background: kpi.iconBg }"
      >
        <el-icon
          :size="24"
          :style="{ color: kpi.color }"
        >
          <component :is="kpi.icon" />
        </el-icon>
      </div>
      <div class="stat-card__content">
        <span class="stat-card__label">{{ kpi.title }}</span>
        <span class="stat-card__value">{{ kpi.value }}</span>
        <span
          class="stat-card__trend"
          :class="kpi.isPositive ? 'stat-card__trend--up' : 'stat-card__trend--down'"
        >
          {{ kpi.isPositive ? '↑' : '↓' }} {{ kpi.change }}
        </span>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
export interface KpiCard {
  title: string
  value: string
  change: string
  isPositive: boolean
  icon: object
  color: string
  iconBg: string
}
</script>

<script setup lang="ts">
defineProps<{
  kpiCards: KpiCard[]
}>()
</script>

<style scoped>
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--bg-0);
  border: 1px solid var(--bg-200);
  border-radius: var(--radius-lg);
  padding: 20px;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.stat-card__icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.stat-card__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.stat-card__label {
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-card__value {
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  line-height: 1.2;
}

.stat-card__trend {
  font-size: 0.75rem;
  font-weight: 500;
}

.stat-card__trend--up {
  color: var(--success);
}

.stat-card__trend--down {
  color: var(--error);
}
</style>