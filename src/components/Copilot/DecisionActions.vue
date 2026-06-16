<template>
  <div class="copilot-decision-actions">
    <el-button
      type="success"
      size="large"
      :icon="Check"
      :loading="loading"
      @click="handleAccept"
    >
      {{ $t('copilot.actions.accept') }}
    </el-button>
    
    <el-button
      type="warning"
      size="large"
      :icon="Edit"
      :loading="loading"
      @click="handleModify"
    >
      {{ $t('copilot.actions.modify') }}
    </el-button>
    
    <el-button
      type="danger"
      size="large"
      :icon="Close"
      :loading="loading"
      @click="handleReject"
    >
      {{ $t('copilot.actions.reject') }}
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Check, Edit, Close } from '@element-plus/icons-vue'

interface Props {
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disabled: false
})

const emit = defineEmits<{
  accept: []
  modify: []
  reject: []
}>()

const loading = ref(false)

function handleAccept() {
  if (props.disabled) return
  emit('accept')
}

function handleModify() {
  if (props.disabled) return
  emit('modify')
}

function handleReject() {
  if (props.disabled) return
  emit('reject')
}

function setLoading(value: boolean) {
  loading.value = value
}

defineExpose({
  setLoading
})
</script>

<style scoped>
.copilot-decision-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  padding: 16px 0;
}

.copilot-decision-actions .el-button {
  min-width: 100px;
}
</style>
