<template>
  <div class="alignment-checker">
    <slot />
  </div>
</template>

<style scoped>
.alignment-checker { padding: 8px; }
.checker-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.checker-header h3 { margin: 0; }
.summary-card { margin-bottom: 16px; }
.suffix-success { color: var(--success); }
.suffix-danger { color: var(--error); }
.issues-card { margin-bottom: 16px; }
.chain-visualizer { margin-top: 24px; }
.chain-visualizer h4 { margin: 0 0 12px; }
.chain-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chain-node {
  padding: 8px 16px;
  border-radius: 8px;
  text-align: center;
  min-width: 120px;
}
.chain-node.mission { background: rgba(245, 108, 108, 0.1); border: 1px solid var(--error); }
.chain-node.strategic_goal { background: rgba(230, 162, 60, 0.1); border: 1px solid var(--warning); }
.chain-node.project { background: rgba(64, 158, 255, 0.1); border: 1px solid var(--accent-primary); }
.chain-node.task { background: rgba(103, 194, 58, 0.1); border: 1px solid var(--success); }
.node-level { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.node-name { font-weight: 600; font-size: 14px; }
.chain-arrow { font-size: 20px; color: var(--text-tertiary); }
</style>
