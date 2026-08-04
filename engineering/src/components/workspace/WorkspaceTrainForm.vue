<template>
  <el-form :model="trainForm" label-width="140px">
    <el-form-item :label="t('workspace.modelName')">
      <el-input
        v-model="trainForm.modelName"
        :placeholder="t('workspace.modelNamePlaceholder')"
      />
    </el-form-item>
    <el-form-item :label="t('workspace.dataPath')">
      <el-input
        v-model="trainForm.dataPath"
        :placeholder="t('workspace.dataPathPlaceholder')"
      />
    </el-form-item>
    <el-divider content-position="left">
      {{ t('workspace.hyperparams') }}
    </el-divider>
    <el-form-item :label="t('workspace.learningRate')">
      <el-input-number
        v-model="trainForm.hyperparameters.learning_rate"
        :min="0.0001"
        :max="0.1"
        :step="0.001"
        :precision="4"
      />
    </el-form-item>
    <el-form-item :label="t('workspace.epochs')">
      <el-input-number
        v-model="trainForm.hyperparameters.epochs"
        :min="1"
        :max="1000"
        :step="10"
      />
    </el-form-item>
    <el-form-item :label="t('workspace.batchSize')">
      <el-input-number
        v-model="trainForm.hyperparameters.batch_size"
        :min="1"
        :max="256"
        :step="8"
      />
    </el-form-item>
    <el-form-item :label="t('workspace.optimizer')">
      <el-select v-model="trainForm.hyperparameters.optimizer">
        <el-option label="Adam" value="adam" />
        <el-option label="SGD" value="sgd" />
        <el-option label="RMSprop" value="rmsprop" />
      </el-select>
    </el-form-item>
    <el-form-item :label="t('workspace.device')">
      <el-select v-model="trainForm.device">
        <el-option :label="t('workspace.auto')" value="auto" />
        <el-option label="GPU (CUDA)" value="cuda" />
        <el-option :label="t('workspace.cpu')" value="cpu" />
      </el-select>
    </el-form-item>
    <el-form-item>
      <el-button
        type="warning"
        :loading="dryRunning"
        @click="$emit('dry-run')"
      >
        {{ t('workspace.previewPlan') }}
      </el-button>
      <el-button
        type="primary"
        :loading="training"
        :disabled="!trainPlanConfirmed"
        @click="$emit('train')"
      >
        {{ t('workspace.startTraining') }}
      </el-button>
    </el-form-item>
  </el-form>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface Hyperparameters {
  learning_rate: number
  epochs: number
  batch_size: number
  optimizer: string
}

interface TrainForm {
  modelName: string
  dataPath: string
  hyperparameters: Hyperparameters
  device: string
}

defineProps<{
  trainForm: TrainForm
  dryRunning: boolean
  training: boolean
  trainPlanConfirmed: boolean
}>()

defineEmits<{
  'dry-run': []
  'train': []
}>()
</script>