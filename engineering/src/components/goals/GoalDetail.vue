<template>
  <div class="goal-detail">
    <slot />
  </div>
</template>

<style scoped>
.goal-detail { padding: 8px; }
.detail-header { margin-bottom: 16px; }
.header-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.goal-title { margin: 0; font-size: 18px; }
.goal-desc { color: var(--text-secondary); margin: 8px 0; }
.meta-row { display: flex; gap: 16px; color: var(--text-tertiary); font-size: 13px; }
.progress-card { margin-bottom: 16px; }
.progress-stats { display: flex; gap: 16px; margin-top: 8px; color: var(--text-secondary); }
.tasks-card { margin-bottom: 16px; }
.history-card { margin-bottom: 16px; }
.history-header { display: flex; justify-content: space-between; align-items: center; }
</style>
