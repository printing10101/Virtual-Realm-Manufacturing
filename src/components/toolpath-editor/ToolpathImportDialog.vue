<template>
  <el-dialog
    v-model="visible"
    title="导入G代码"
    width="650px"
    :close-on-click-modal="false"
  >
    <el-tabs v-model="importMode">
      <el-tab-pane
        label="粘贴G代码"
        name="paste"
      >
        <el-input
          v-model="gcodeText"
          type="textarea"
          :rows="14"
          placeholder="在此粘贴G代码..."
          style="font-family: monospace; font-size: 12px"
        />
      </el-tab-pane>
      <el-tab-pane
        label="上传文件"
        name="upload"
      >
        <el-upload
          drag
          :auto-upload="false"
          :limit="1"
          accept=".nc,.h,.txt,.gcode,.ngc"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
        >
          <el-icon class="el-icon--upload">
            <UploadFilled />
          </el-icon>
          <div class="el-upload__text">
            拖拽文件到此处或 <em>点击选择</em>
          </div>
          <template #tip>
            <div class="el-upload__tip">
              支持 .nc / .h / .txt 格式
            </div>
          </template>
        </el-upload>
      </el-tab-pane>
    </el-tabs>

    <div
      v-if="previewLines.length > 0"
      class="preview-section"
    >
      <h4>预览 ({{ previewLines.length }} 行)</h4>
      <div class="preview-content">
        <div
          v-for="(line, i) in previewLines"
          :key="i"
          class="preview-line"
        >
          {{ line }}
        </div>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">
        取消
      </el-button>
      <el-button
        type="primary"
        :disabled="!gcodeText.trim()"
        @click="handleImport"
      >
        导入并加载
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useToolpathEditorStore } from './stores/toolpathEditor'

const visible = defineModel<boolean>('visible', { required: true })
const store = useToolpathEditorStore()

const importMode = ref('paste')
const gcodeText = ref('')
const fileRef = ref<File | null>(null)

const previewLines = computed(() => {
  return gcodeText.value
    .trim()
    .split('\n')
    .filter((l) => l.trim())
    .slice(0, 20)
})

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    const reader = new FileReader()
    reader.onload = (e) => {
      gcodeText.value = e.target?.result as string
    }
    reader.readAsText(file.raw)
    fileRef.value = file.raw
  }
}

function handleFileRemove() {
  fileRef.value = null
  gcodeText.value = ''
}

function handleImport() {
  const result = store.loadGCode(gcodeText.value)
  if (result.success) {
    ElMessage.success(result.message)
    visible.value = false
  } else {
    ElMessage.error(result.message)
  }
}
</script>

<style lang="scss" scoped>
.preview-section {
  margin-top: 12px;
  h4 {
    margin: 0 0 8px;
    font-size: 13px;
    font-weight: 600;
    color: #555;
  }
}

.preview-content {
  max-height: 200px;
  overflow-y: auto;
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 8px;
  font-family: monospace;
  font-size: 11px;

  .preview-line {
    padding: 1px 0;
    white-space: pre;
    overflow-x: auto;
  }
}
</style>
