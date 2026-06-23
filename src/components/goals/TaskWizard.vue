<template>
  <div class="task-wizard">
    <slot />
  </div>
</template>

<style scoped>
.task-wizard { max-width: 800px; margin: 0 auto; }
.step-content { min-height: 300px; padding: 16px 0; }
.goal-radio-group { display: flex; flex-direction: column; gap: 8px; }
.goal-option { cursor: pointer; border: 2px solid transparent; }
.goal-option.selected { border-color: var(--accent-primary); }
.goal-option-content { display: flex; flex-direction: column; gap: 4px; }
.goal-option-desc { margin: 4px 0 0; color: var(--text-secondary); font-size: 13px; }
.form-hint { display: block; color: var(--text-tertiary); font-size: 12px; margin-top: 4px; }
.wizard-actions { display: flex; justify-content: center; gap: 12px; padding: 16px 0; }
</style>
