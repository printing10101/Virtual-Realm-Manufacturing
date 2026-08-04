<template>
  <el-dialog
    :model-value="visible"
    :title="t('equipmentMonitor.dialogSettingsTitle')"
    width="480px"
    :close-on-click-modal="false"
    @update:model-value="emit('update:visible', $event)"
  >
    <el-form label-width="110px" @submit.prevent>
      <el-form-item :label="t('equipmentMonitor.colDeviceName')">
        <el-input :model-value="form.name" disabled />
      </el-form-item>
      <el-form-item :label="t('equipmentMonitor.fieldStatus')">
        <el-select v-model="form.status" style="width: 100%">
          <el-option :label="t('equipmentMonitor.labelStatusRunning')" :value="t('equipmentMonitor.labelStatusRunning')" />
          <el-option :label="t('equipmentMonitor.labelStatusStandby')" :value="t('equipmentMonitor.labelStatusStandby')" />
          <el-option :label="t('equipmentMonitor.labelStatusMaintenance')" :value="t('equipmentMonitor.labelStatusMaintenance')" />
          <el-option :label="t('equipmentMonitor.labelStatusFault')" :value="t('equipmentMonitor.labelStatusFault')" />
        </el-select>
      </el-form-item>
      <el-form-item :label="t('equipmentMonitor.fieldTemperature')">
        <el-input-number v-model="form.temperature" :min="0" :max="500" :precision="1" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('equipmentMonitor.fieldVibration')">
        <el-input-number v-model="form.vibration" :min="0" :max="50" :precision="2" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('equipmentMonitor.fieldRpm')">
        <el-input-number v-model="form.rpm" :min="0" :max="50000" style="width: 100%" />
      </el-form-item>
      <el-form-item :label="t('equipmentMonitor.fieldPower')">
        <el-input-number v-model="form.power" :min="0" :max="1000" :precision="1" style="width: 100%" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">
        {{ t('equipmentMonitor.btnCancel') }}
      </el-button>
      <el-button type="primary" :loading="submitting" @click="emit('save', form)">
        {{ t('equipmentMonitor.btnSubmit') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

export interface SettingsForm {
  id: number
  name: string
  status: string
  temperature: number | null
  vibration: number | null
  rpm: number | null
  power: number | null
}

defineProps<{
  visible: boolean
  form: SettingsForm
  submitting: boolean
}>()

const emit = defineEmits<{
  (e: 'update:visible', val: boolean): void
  (e: 'save', form: SettingsForm): void
}>()
</script>