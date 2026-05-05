<template>
  <div class="model-config">
    <el-form
      :model="configForm"
      label-width="160px"
    >
      <el-divider content-position="left">
        {{ t('modelManagement.localModelConfig') }}
      </el-divider>

      <el-form-item :label="t('modelManagement.localModel')">
        <el-select
          v-model="configForm.local_model"
          filterable
          allow-create
          style="width: 100%;"
        >
          <el-option
            label="qwen2.5:7b"
            value="qwen2.5:7b"
          />
          <el-option
            label="qwen2.5-coder:7b"
            value="qwen2.5-coder:7b"
          />
          <el-option
            label="llama3:8b"
            value="llama3:8b"
          />
          <el-option
            label="mistral:7b"
            value="mistral:7b"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('modelManagement.localTimeout')">
        <el-input-number
          v-model="configForm.local_timeout"
          :min="10"
          :max="300"
          style="width: 100%;"
        />
      </el-form-item>

      <el-divider content-position="left">
        {{ t('modelManagement.cloudModelConfig') }}
      </el-divider>

      <el-form-item :label="t('modelManagement.cloudProvider')">
        <el-select
          v-model="configForm.cloud_provider"
          style="width: 100%;"
        >
          <el-option
            label="OpenAI"
            value="openai"
          />
          <el-option
            label="Anthropic"
            value="anthropic"
          />
          <el-option
            label="自定义"
            value="custom"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('modelManagement.cloudModel')">
        <el-select
          v-model="configForm.cloud_model"
          filterable
          allow-create
          style="width: 100%;"
        >
          <el-option
            label="gpt-4o"
            value="gpt-4o"
          />
          <el-option
            label="gpt-4o-mini"
            value="gpt-4o-mini"
          />
          <el-option
            label="claude-3-5-sonnet"
            value="claude-3-5-sonnet"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('modelManagement.cloudApiKey')">
        <el-input
          v-model="configForm.cloud_api_key"
          type="password"
          show-password
          :placeholder="t('modelManagement.apiKeyPlaceholder')"
        />
      </el-form-item>

      <el-divider content-position="left">
        {{ t('modelManagement.routeConfig') }}
      </el-divider>

      <el-form-item :label="t('modelManagement.fallbackThreshold')">
        <el-input-number
          v-model="configForm.fallback_threshold"
          :min="1"
          :max="8"
          style="width: 100%;"
        />
      </el-form-item>

      <el-divider content-position="left">
        {{ t('modelManagement.finetuneConfig') }}
      </el-divider>

      <el-form-item :label="t('modelManagement.autoTrigger')">
        <el-switch v-model="configForm.finetune_auto_trigger" />
      </el-form-item>

      <el-form-item :label="t('modelManagement.minSamples')">
        <el-input-number
          v-model="configForm.finetune_min_samples"
          :min="10"
          :max="500"
          style="width: 100%;"
        />
      </el-form-item>

      <el-form-item :label="t('modelManagement.intervalDays')">
        <el-input-number
          v-model="configForm.finetune_interval_days"
          :min="1"
          :max="30"
          style="width: 100%;"
        />
      </el-form-item>

      <el-form-item>
        <el-button
          type="primary"
          @click="saveConfig"
        >
          {{ t('common.save') }}
        </el-button>
        <el-button @click="resetForm">
          {{ t('common.reset') }}
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()

const props = defineProps<{
  config: {
    local_model?: string
    cloud_provider?: string
    cloud_model?: string
    fallback_threshold?: number
    local_timeout?: number
    finetune_auto_trigger?: boolean
    finetune_min_samples?: number
    finetune_interval_days?: number
  }
}>()

const emit = defineEmits(['update'])

const configForm = ref({
  local_model: props.config.local_model || 'qwen2.5:7b',
  cloud_provider: props.config.cloud_provider || 'openai',
  cloud_model: props.config.cloud_model || 'gpt-4o',
  cloud_api_key: '',
  fallback_threshold: props.config.fallback_threshold || 3,
  local_timeout: props.config.local_timeout || 30,
  finetune_auto_trigger: props.config.finetune_auto_trigger || false,
  finetune_min_samples: props.config.finetune_min_samples || 50,
  finetune_interval_days: props.config.finetune_interval_days || 7
})

function resetForm() {
  configForm.value = {
    local_model: props.config.local_model || 'qwen2.5:7b',
    cloud_provider: props.config.cloud_provider || 'openai',
    cloud_model: props.config.cloud_model || 'gpt-4o',
    cloud_api_key: '',
    fallback_threshold: props.config.fallback_threshold || 3,
    local_timeout: props.config.local_timeout || 30,
    finetune_auto_trigger: props.config.finetune_auto_trigger || false,
    finetune_min_samples: props.config.finetune_min_samples || 50,
    finetune_interval_days: props.config.finetune_interval_days || 7
  }
}

function saveConfig() {
  emit('update', {
    local_model: configForm.value.local_model,
    cloud_provider: configForm.value.cloud_provider,
    cloud_model: configForm.value.cloud_model,
    fallback_threshold: configForm.value.fallback_threshold,
    local_timeout: configForm.value.local_timeout,
    finetune_auto_trigger: configForm.value.finetune_auto_trigger,
    finetune_min_samples: configForm.value.finetune_min_samples,
    finetune_interval_days: configForm.value.finetune_interval_days
  })
}
</script>

<style scoped lang="scss">
.model-config {
  max-width: 800px;
  margin: 0 auto;
}
</style>
