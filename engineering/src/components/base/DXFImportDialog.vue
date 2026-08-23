<!--
  DXFImportDialog - DXF 文件导入对话框
  
  继承自 BaseImportDialog，针对 DXF 格式进行定制
  
  ## 特性
  - 支持 DXF 文件上传和解析
  - 展示解析统计（线段、圆弧、圆数量）
  - 2D/3D 预览
  - 特征识别（孔、平面）
  - 导入到当前工程
-->
<template>
  <BaseImportDialog
    v-model="visible"
    :accept="'.dxf,.DXF'"
    :dialog-title="$t('dxfImportDialog.dialogTitle')"
    :upload-text="$t('dxfImportDialog.uploadText')"
    :success-message="$t('dxfImportDialog.importSuccess')"
    @file-selected="handleFileSelected"
    @success="handleImportSuccess"
    @error="handleImportError"
    @import="handleImportToProject"
  >
    <!-- 预览插槽：DXF 预览 -->
    <template #preview="{ parseResult }">
      <div class="dxf-preview">
        <DxfParseStats
          :parse-result="parseResult as DxfParseResponse"
          :features-count="featuresCount"
        />
        <DxfPreview :parse-result="parseResult as DxfParseResponse" />
      </div>
    </template>

    <!-- 自定义导入按钮 -->
    <template #success-actions="props">
      <el-button
        type="primary"
        :loading="importing"
        @click="props.import"
      >
        {{ $t('dxfImportDialog.importToProject') }}
      </el-button>
      <el-button @click="handleClose">
        {{ $t('common.cancel') }}
      </el-button>
    </template>
  </BaseImportDialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useDxfImportStore } from '@/stores/dxfImport'
import type { DxfParseResponse } from '@/types'
import BaseImportDialog from './BaseImportDialog.vue'
import DxfParseStats from '../dxf_import/DxfParseStats.vue'
import DxfPreview from '../dxf_import/DxfPreview.vue'

const { t } = useI18n()
const store = useDxfImportStore()

const visible = computed({
  get: () => store.showDialog,
  set: (v) => { store.showDialog = v },
})

const importing = ref(false)

/** 特征统计 */
const featuresCount = computed(() => {
  const f = store.featureResult
  if (!f) return 0
  return (f.hole_count ?? 0) + (f.plane_count ?? 0)
})

/** 文件选择处理 */
async function handleFileSelected(file: File) {
  const ok = await store.importDxfFile(file)
  if (!ok) {
    ElMessage.error(store.errorMessage || t('dxfImportDialog.dxfImportFailed'))
  }
}

/** 导入成功处理 */
function handleImportSuccess(_parseResult: unknown) {
  // 保留通用处理，可在扩展中继续处理
}

/** 导入错误处理 */
function handleImportError(_error: Error) {
  // 保留通用处理，可在扩展中继续处理
}

/** 导入到工程 */
async function handleImportToProject(_parseResult: unknown) {
  importing.value = true
  try {
    const { useProjectStore } = await import('@/stores/project')
    const projectStore = useProjectStore()
    
    if (!projectStore.manifest) {
      ElMessage.error(t('dxfImportDialog.noOpenProject'))
      return
    }

    const parseResult = store.parseResult
    if (parseResult) {
      projectStore.manifest.resources.push({
        id: store.currentFileId || `dxf-${Date.now()}`,
        type: 'drawing',
        path: `dxf/${parseResult.file_name}`,
        original_name: parseResult.file_name,
        mime_type: 'application/dxf',
        added_at: new Date().toISOString(),
        metadata: {
          source: 'dxf-import',
          file_id: store.currentFileId,
          lines_count: parseResult.lines_count,
          arcs_count: parseResult.arcs_count,
          circles_count: parseResult.circles_count,
          features_count: featuresCount.value,
        },
      })
      projectStore.markModified?.()
    }

    ElMessage.success(t('dxfImportDialog.importToProjectSuccess'))
    store.closeDialog()
  } catch {
    ElMessage.error(t('dxfImportDialog.importToProjectFailed'))
  } finally {
    importing.value = false
  }
}

/** 关闭处理 */
function handleClose() {
  store.closeDialog()
}
</script>

<style scoped>
.dxf-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
