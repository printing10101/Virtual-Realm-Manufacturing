<template>
  <div class="dependency-tree">
    <TreeNode
      v-if="tree"
      :node="tree"
    />
  </div>
</template>

<script setup lang="ts">
import TreeNode from './DependencyTreeNode.vue'

defineProps<{
  tree: any
}>()
</script>

<style scoped>
.dependency-tree {
  padding: 10px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}
</style>
