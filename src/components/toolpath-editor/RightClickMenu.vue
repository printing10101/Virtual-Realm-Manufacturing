<template>
  <div
    v-if="visible"
    class="right-click-menu"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
  >
    <div
      class="menu-item"
      @click="handleDelete"
    >
      <el-icon><Delete /></el-icon>
      <span>{{ $t('rightClickMenu.delete') }}</span>
    </div>
    <div
      class="menu-item"
      @click="handleAdjustFeed"
    >
      <el-icon><Edit /></el-icon>
      <span>{{ $t('rightClickMenu.adjustFeed') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Delete, Edit } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
  position: { x: number; y: number }
  segmentId: string
}>()

const emit = defineEmits<{
  'delete': [segmentId: string]
  'adjust-feed': [segmentId: string]
}>()

function handleDelete() {
  emit('delete', props.segmentId)
}

function handleAdjustFeed() {
  emit('adjust-feed', props.segmentId)
}
</script>

<style lang="scss" scoped>
.right-click-menu {
  position: fixed;
  z-index: 1000;
  background: #1e1e2e;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 4px 0;
  min-width: 200px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);

  .menu-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    cursor: pointer;
    color: #e0e0e0;
    font-size: 13px;
    transition: background 0.15s;

    &:hover {
      background: rgba(255, 215, 64, 0.15);
      color: #ffd740;
    }
  }
}
</style>
