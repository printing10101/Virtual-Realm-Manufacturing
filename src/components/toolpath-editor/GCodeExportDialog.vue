<template>
  <el-dialog
    v-model="visible"
    title="导出G代码"
    width="700px"
    :close-on-click-modal="false"
  >
    <el-form
      label-width="100px"
      size="default"
    >
      <el-form-item label="控制器格式">
        <el-select
          v-model="controller"
          style="width: 200px"
        >
          <el-option
            label="Fanuc 0i-MF"
            value="fanuc"
          />
          <el-option
            label="Siemens 840D"
            value="siemens"
          />
          <el-option
            label="Heidenhain TNC"
            value="heidenhain"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="程序号">
        <el-input-number
          v-model="programNumber"
          :min="1"
          :max="9999"
          controls-position="right"
          style="width: 200px"
        />
      </el-form-item>
    </el-form>

    <div
      v-if="validation && !validation.valid"
      class="validation-section"
    >
      <el-alert
        v-for="(err, i) in validation.errors"
        :key="'e' + i"
        :title="err"
        type="error"
        :closable="false"
        show-icon
        style="margin-bottom: 4px"
      />
    </div>

    <div
      v-if="validation && validation.warnings.length > 0"
      class="validation-section"
    >
      <el-alert
        v-for="(w, i) in validation.warnings"
        :key="'w' + i"
        :title="w"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 4px"
      />
    </div>

    <el-input
      v-model="gcode"
      type="textarea"
      :rows="16"
      readonly
      style="margin-top: 12px; font-family: monospace; font-size: 12px"
    />

    <template #footer>
      <el-button @click="visible = false">
        关闭
      </el-button>
      <el-button
        type="primary"
        @click="handleCopy"
      >
        <el-icon><DocumentCopy /></el-icon>
        复制到剪贴板
      </el-button>
      <el-button
        type="success"
        @click="handleDownload"
      >
        <el-icon><Download /></el-icon>
        下载文件
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { DocumentCopy, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { GCodeController } from './types/editor'
import { useToolpathEditorStore } from './stores/toolpathEditor'

const visible = defineModel<boolean>('visible', { required: true })

const store = useToolpathEditorStore()
const controller = ref<GCodeController>('fanuc')
const programNumber = ref(1)
const gcode = ref('')
const validation = ref<{ valid: boolean; errors: string[]; warnings: string[] } | null>(null)

watch(visible, (v) => {
  if (v) {
    refreshExport()
  }
})

watch([controller, programNumber], () => {
  refreshExport()
})

function refreshExport() {
  const result = store.exportGCode(controller.value, programNumber.value)
  gcode.value = result.gcode
  validation.value = result.validation
}

async function handleCopy() {
  try {
    await navigator.clipboard.writeText(gcode.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}

function handleDownload() {
  const ext = controller.value === 'heidenhain' ? '.h' : '.nc'
  const filename = `O${String(programNumber.value).padStart(4, '0')}${ext}`
  const blob = new Blob([gcode.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已下载: ${filename}`)
}
</script>

<style lang="scss" scoped>
.validation-section {
  margin-bottom: 8px;
}
</style>
