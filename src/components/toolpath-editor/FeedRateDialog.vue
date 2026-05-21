<template>
  <el-dialog
    v-model="visible"
    title="调整进给率"
    width="400px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-form
      label-width="100px"
      size="default"
    >
      <el-form-item label="当前刀路段">
        <el-tag type="info">
          {{ segmentInfo }}
        </el-tag>
      </el-form-item>
      <el-form-item label="当前进给率">
        <span class="current-value">{{ currentFeedRate }} mm/min</span>
      </el-form-item>
      <el-form-item label="新进给率">
        <el-input-number
          v-model="newFeedRate"
          :min="10"
          :max="50000"
          :step="10"
          controls-position="right"
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="工艺范围">
        <el-alert
          title="推荐范围: 10 - 50000 mm/min（粗加工100-500，精加工50-200）"
          type="info"
          :closable="false"
          show-icon
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">
        取消
      </el-button>
      <el-button
        type="primary"
        :disabled="newFeedRate === currentFeedRate || newFeedRate < 10 || newFeedRate > 50000"
        @click="handleConfirm"
      >
        确认修改
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
const props = defineProps<{
  segmentId: string
  currentFeedRate: number
  segmentType: string
  segmentBlock: number
}>()

const emit = defineEmits<{
  'confirm': [segmentId: string, newFeedRate: number]
}>()

const visible = defineModel<boolean>('visible', { required: true })
const newFeedRate = ref(props.currentFeedRate)

const segmentInfo = computed(
  () => `#${props.segmentBlock} (${props.segmentType})`,
)

watch(
  () => props.currentFeedRate,
  (v) => {
    newFeedRate.value = v
  },
)

function handleConfirm() {
  emit('confirm', props.segmentId, newFeedRate.value)
  visible.value = false
}

function handleClose() {
  newFeedRate.value = props.currentFeedRate
}
</script>

<style lang="scss" scoped>
.current-value {
  font-weight: 600;
  color: #409eff;
}
</style>
