<template>
  <el-dialog
    v-model="dialogVisible"
    :title="title"
    width="720px"
    :close-on-click-modal="false"
  >
    <el-form
      :model="form"
      label-width="100px"
    >
      <el-form-item :label="formTemplateLabel">
        <el-select
          v-model="form.templateName"
          :placeholder="formTemplatePlaceholder"
          clearable
          style="width: 100%"
          @change="handleTemplateSelect"
        >
          <el-option
            v-for="tpl in builtinTemplates"
            :key="tpl.name"
            :label="`${tpl.name} (v${tpl.version})`"
            :value="tpl.name"
          />
        </el-select>
      </el-form-item>
      <el-form-item :label="formSpecLabel">
        <el-input
          v-model="form.specYaml"
          type="textarea"
          :rows="14"
          :placeholder="formSpecPlaceholder"
          class="spec-editor"
        />
      </el-form-item>
      <el-form-item :label="formOwnerLabel">
        <el-input
          v-model="form.ownerId"
          :placeholder="formOwnerPlaceholder"
          clearable
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">
        {{ btnCancelText }}
      </el-button>
      <el-button
        :loading="validating"
        @click="emit('validate')"
      >
        {{ btnValidateText }}
      </el-button>
      <el-button
        type="primary"
        :loading="submitting"
        @click="emit('submit')"
      >
        {{ confirmButtonText }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { WorkflowSpec } from '@/contracts/task'

const props = defineProps<{
  visible: boolean
  mode: 'submit' | 'resume'
  title: string
  confirmButtonText: string
  form: { templateName: string; specYaml: string; ownerId: string }
  builtinTemplates: Array<{ name: string; version: string; spec: WorkflowSpec }>
  validating: boolean
  submitting: boolean
  formTemplateLabel: string
  formTemplatePlaceholder: string
  formSpecLabel: string
  formSpecPlaceholder: string
  formOwnerLabel: string
  formOwnerPlaceholder: string
  btnCancelText: string
  btnValidateText: string
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: []
  cancel: []
  validate: []
  'template-select': [name: string]
}>()

const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

function handleTemplateSelect(name: string) {
  emit('template-select', name)
}

function handleCancel() {
  emit('cancel')
  emit('update:visible', false)
}
</script>

<style scoped>
:deep(.spec-editor .el-textarea__inner) {
  font-family: var(--font-mono);
  font-size: 12px;
}
</style>