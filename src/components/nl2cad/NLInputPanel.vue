<template>
  <div class="nl-input-panel">
    <!-- 聊天历史区域 -->
    <div
      ref="chatContainerRef"
      class="chat-container"
    >
      <!-- 欢迎消息 -->
      <div class="message assistant-message">
        <div class="message-avatar">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <div class="message-content">
          <div class="message-bubble">
            <p>{{ t('nlInputPanel.welcomeGreeting') }}</p>
            <p>{{ t('nlInputPanel.welcomeHint') }}</p>
          </div>
          <div class="message-time">
            {{ formatTime(now) }}
          </div>
        </div>
      </div>

      <!-- 用户和AI消息 -->
      <template
        v-for="msg in messages"
        :key="msg.id"
      >
        <!-- 用户消息 -->
        <div
          v-if="msg.role === 'user'"
          class="message user-message"
        >
          <div class="message-content">
            <div class="message-bubble user-bubble">
              {{ msg.content }}
            </div>
            <div class="message-time">
              {{ formatTime(msg.timestamp) }}
            </div>
          </div>
          <div class="message-avatar user-avatar">
            <el-icon><User /></el-icon>
          </div>
        </div>

        <!-- AI消息 -->
        <div
          v-else
          class="message assistant-message"
        >
          <div class="message-avatar">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="message-content">
            <!-- 参数提取结果 -->
            <div
              v-if="msg.type === 'params'"
              class="message-bubble"
            >
              <p>{{ t('nlInputPanel.paramsExtracted') }}</p>
              <div class="params-card">
                <div class="param-row">
                  <span class="param-label">{{ t('nlInputPanel.shapeTypeLabel') }}</span>
                  <span class="param-value">{{ getShapeLabel(msg.params?.shape_type) }}</span>
                </div>
                <div
                  v-if="msg.params?.dimensions"
                  class="param-row"
                >
                  <span class="param-label">{{ t('nlInputPanel.dimensionsLabel') }}</span>
                  <span class="param-value">
                    <template v-if="msg.params.dimensions.length">
                      {{ t('nlInputPanel.dimLength') }} {{ msg.params.dimensions.length }}mm
                    </template>
                    <template v-if="msg.params.dimensions.width">
                      × {{ t('nlInputPanel.dimWidth') }} {{ msg.params.dimensions.width }}mm
                    </template>
                    <template v-if="msg.params.dimensions.height">
                      × {{ t('nlInputPanel.dimHeight') }} {{ msg.params.dimensions.height }}mm
                    </template>
                    <template v-if="msg.params.dimensions.radius">
                      {{ t('nlInputPanel.dimRadius') }} {{ msg.params.dimensions.radius }}mm
                    </template>
                  </span>
                </div>
                <div
                  v-if="msg.params?.features?.length"
                  class="param-row"
                >
                  <span class="param-label">{{ t('nlInputPanel.featuresLabel') }}</span>
                  <span class="param-value">
                    {{ msg.params.features.map((f: CADFeature) => getFeatureLabel(f.type)).join(', ') }}
                  </span>
                </div>
                <div
                  v-if="msg.params?.material"
                  class="param-row"
                >
                  <span class="param-label">{{ t('nlInputPanel.materialLabel') }}</span>
                  <span class="param-value">{{ msg.params.material }}</span>
                </div>
                <div class="param-row confidence-row">
                  <span class="param-label">{{ t('nlInputPanel.confidenceLabel') }}</span>
                  <el-progress
                    :percentage="Math.round((msg.params?.confidence || 0.8) * 100)"
                    :color="getConfidenceColor(msg.params?.confidence || 0.8)"
                    :stroke-width="8"
                    style="flex: 1; margin-left: 8px;"
                  />
                </div>
              </div>
              <div class="message-actions">
                <el-button
                  type="primary"
                  size="small"
                  @click="handleConfirmParams(msg.params)"
                >
                  <el-icon><Check /></el-icon>{{ t('nlInputPanel.confirmGenerate') }}
                </el-button>
                <el-button
                  size="small"
                  @click="handleEditParams(msg.params)"
                >
                  <el-icon><Edit /></el-icon>{{ t('nlInputPanel.editParams') }}
                </el-button>
              </div>
            </div>

            <!-- 模型生成结果 -->
            <div
              v-else-if="msg.type === 'model'"
              class="message-bubble"
            >
              <p>{{ t('nlInputPanel.modelGenerated') }}</p>
              <div class="model-card">
                <div class="model-preview">
                  <el-icon :size="32">
                    <Box />
                  </el-icon>
                </div>
                <div class="model-info">
                  <div class="model-name">
                    {{ msg.modelName || t('nlInputPanel.defaultModelName') }}
                  </div>
                  <div class="model-format">
                    {{ msg.format?.toUpperCase() }}
                  </div>
                </div>
              </div>
              <div class="message-actions">
                <el-button
                  type="primary"
                  size="small"
                  @click="handleView3D(msg.modelPath)"
                >
                  <el-icon><View /></el-icon>{{ t('nlInputPanel.viewIn3D') }}
                </el-button>
                <el-button
                  size="small"
                  @click="handleDownload(msg.modelPath)"
                >
                  <el-icon><Download /></el-icon>{{ t('nlInputPanel.download') }}
                </el-button>
              </div>
            </div>

            <!-- 普通文本消息 -->
            <div
              v-else
              class="message-bubble"
            >
              {{ msg.content }}
            </div>
            <div class="message-time">
              {{ formatTime(msg.timestamp) }}
            </div>
          </div>
        </div>
      </template>

      <!-- 加载指示器 -->
      <div
        v-if="loading"
        class="message assistant-message"
      >
        <div class="message-avatar">
          <el-icon><ChatDotRound /></el-icon>
        </div>
        <div class="message-content">
          <div class="message-bubble typing-indicator">
            <span /><span /><span />
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <div class="input-wrapper">
        <el-input
          v-model="userInput"
          type="textarea"
          :rows="2"
          :placeholder="t('nlInputPanel.inputPlaceholder')"
          :disabled="loading"
          @keydown.enter.exact.prevent="handleSend"
        />
        <el-button
          type="primary"
          :icon="Promotion"
          :loading="loading"
          :disabled="!userInput.trim()"
          @click="handleSend"
        />
      </div>
      <div class="input-hints">
        <el-tag
          size="small"
          type="info"
          @click="fillExample(t('nlInputPanel.exampleBoxPrompt'))"
        >
          {{ t('nlInputPanel.exampleBox') }}
        </el-tag>
        <el-tag
          size="small"
          type="info"
          @click="fillExample(t('nlInputPanel.exampleCylinderPrompt'))"
        >
          {{ t('nlInputPanel.exampleCylinder') }}
        </el-tag>
        <el-tag
          size="small"
          type="info"
          @click="fillExample(t('nlInputPanel.exampleSpherePrompt'))"
        >
          {{ t('nlInputPanel.exampleSphere') }}
        </el-tag>
      </div>
    </div>

    <!-- 参数编辑对话框 -->
    <el-dialog
      v-model="showParamDialog"
      :title="t('nlInputPanel.editModelParamsTitle')"
      width="500px"
    >
      <el-form
        :model="editParams"
        label-width="100px"
      >
        <el-form-item :label="t('nlInputPanel.shapeTypeFormLabel')">
          <el-select v-model="editParams.shape_type">
            <el-option
              :label="t('nlInputPanel.optionBox')"
              value="box"
            />
            <el-option
              :label="t('nlInputPanel.optionCylinder')"
              value="cylinder"
            />
            <el-option
              :label="t('nlInputPanel.optionSphere')"
              value="sphere"
            />
            <el-option
              :label="t('nlInputPanel.optionCone')"
              value="cone"
            />
          </el-select>
        </el-form-item>
        <el-form-item
          v-if="editParams.dimensions"
          :label="t('nlInputPanel.lengthLabel')"
        >
          <el-input-number
            v-model="editParams.dimensions.length"
            :min="1"
            :max="1000"
          />
        </el-form-item>
        <el-form-item
          v-if="editParams.dimensions"
          :label="t('nlInputPanel.widthLabel')"
        >
          <el-input-number
            v-model="editParams.dimensions.width"
            :min="1"
            :max="1000"
          />
        </el-form-item>
        <el-form-item
          v-if="editParams.dimensions"
          :label="t('nlInputPanel.heightLabel')"
        >
          <el-input-number
            v-model="editParams.dimensions.height"
            :min="1"
            :max="1000"
          />
        </el-form-item>
        <el-form-item
          v-if="editParams.dimensions"
          :label="t('nlInputPanel.radiusLabel')"
        >
          <el-input-number
            v-model="editParams.dimensions.radius"
            :min="1"
            :max="500"
          />
        </el-form-item>
        <el-form-item :label="t('nlInputPanel.materialFormLabel')">
          <el-input
            v-model="editParams.material"
            :placeholder="t('nlInputPanel.materialPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showParamDialog = false">
          {{ t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          @click="confirmEditedParams"
        >
          {{ t('nlInputPanel.confirmEdit') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  ChatDotRound,
  User,
  Check,
  Edit,
  View,
  Download,
  Box,
  Promotion,
} from '@element-plus/icons-vue'
import {
  extractParams as apiExtractParams,
  generateModel as apiGenerateModel,
} from '@/api/nl2cad'
import type { CADParams, CADFeature } from '@/types/nl2cad'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  type?: 'params' | 'model' | 'text'
  params?: CADParams
  modelPath?: string
  modelName?: string
  format?: string
}

const { t } = useI18n()

const emit = defineEmits<{
  (e: 'model-generated', modelPath: string, params: CADParams): void
  (e: 'view-3d', modelPath: string): void
}>()

const chatContainerRef = ref<HTMLElement>()
const userInput = ref('')
const messages = ref<Message[]>([])
const loading = ref(false)
const now = new Date()

// 消息唯一 id 生成器，用于 v-for key
let messageIdCounter = 0
function nextMessageId(): string {
  return `msg-${++messageIdCounter}`
}

// 参数编辑
const showParamDialog = ref(false)
const editParams = ref<CADParams>({} as CADParams)

function formatTime(date: Date): string {
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function getShapeLabel(type: string | undefined): string {
  if (!type) return ''
  const map: Record<string, string> = {
    box: t('nlInputPanel.shapeBox'),
    cylinder: t('nlInputPanel.shapeCylinder'),
    sphere: t('nlInputPanel.shapeSphere'),
    cone: t('nlInputPanel.shapeCone'),
  }
  return map[type] || type
}

function getFeatureLabel(type: string): string {
  const map: Record<string, string> = {
    chamfer: t('nlInputPanel.featureChamfer'),
    fillet: t('nlInputPanel.featureFillet'),
    hole: t('nlInputPanel.featureHole'),
    slot: t('nlInputPanel.featureSlot'),
  }
  return map[type] || type
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return 'var(--success)'
  if (confidence >= 0.6) return 'var(--warning)'
  return 'var(--error)'
}

function scrollToBottom() {
  nextTick(() => {
    if (chatContainerRef.value) {
      chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight
    }
  })
}

function fillExample(text: string) {
  userInput.value = text
}

async function handleSend() {
  const text = userInput.value.trim()
  if (!text || loading.value) return

  // 添加用户消息
  messages.value.push({
    id: nextMessageId(),
    role: 'user',
    content: text,
    timestamp: new Date(),
  })
  userInput.value = ''
  loading.value = true
  scrollToBottom()

  try {
    // 通过统一 http 客户端调用参数提取 API
    const data = await apiExtractParams({ description: text })
    const params = (data.params || {}) as CADParams

    // 添加AI回复（参数卡片）
    messages.value.push({
      id: nextMessageId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      type: 'params',
      params,
    })
  } catch (error) {
    console.error('Failed to extract params:', error)
    messages.value.push({
      id: nextMessageId(),
      role: 'assistant',
      content: t('nlInputPanel.errorUnderstand'),
      timestamp: new Date(),
      type: 'text',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

async function handleConfirmParams(params?: CADParams) {
  if (!params) return
  loading.value = true
  scrollToBottom()

  try {
    // 通过统一 http 客户端调用模型生成 API
    const data = await apiGenerateModel({
      description: messages.value.filter(m => m.role === 'user').pop()?.content || '',
      output_format: 'stl',
    })

    // 添加模型生成结果消息
    messages.value.push({
      id: nextMessageId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      type: 'model',
      modelPath: data.model_path,
      modelName: t('nlInputPanel.defaultModelName'),
      format: 'stl',
    })

    // 通知父组件
    emit('model-generated', data.model_path, (data.params || {}) as CADParams)
  } catch (error) {
    console.error('Failed to generate model:', error)
    messages.value.push({
      id: nextMessageId(),
      role: 'assistant',
      content: t('nlInputPanel.errorGenerateFailed'),
      timestamp: new Date(),
      type: 'text',
    })
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function handleEditParams(params?: CADParams) {
  if (!params) return
  editParams.value = structuredClone(params)
  showParamDialog.value = true
}

function confirmEditedParams() {
  // 更新最后一条参数消息
  const lastParamsMsg = [...messages.value].reverse().find(m => m.type === 'params')
  if (lastParamsMsg) {
    lastParamsMsg.params = editParams.value
  }
  showParamDialog.value = false
}

function handleView3D(modelPath?: string) {
  if (!modelPath) return
  emit('view-3d', modelPath)
}

function handleDownload(modelPath?: string) {
  if (!modelPath) return
  // 触发下载
  const link = document.createElement('a')
  link.href = modelPath
  link.download = modelPath.split('/').pop() || 'model.stl'
  link.click()
}
</script>

<style scoped>
.nl-input-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;
}

.user-message {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.assistant-message {
  align-self: flex-start;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  color: white;
  font-size: 18px;
}

.user-avatar {
  background: linear-gradient(135deg, var(--success) 0%, var(--info) 100%);
}

.message-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-sm);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.user-bubble {
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  color: white;
}

.message-time {
  font-size: 11px;
  color: var(--text-tertiary);
  padding: 0 4px;
}

/* 参数卡片 */
.params-card {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.param-label {
  font-weight: 500;
  color: var(--text-secondary);
  min-width: 60px;
}

.param-value {
  color: var(--text-primary);
}

.confidence-row {
  margin-top: 4px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}

.message-actions {
  margin-top: 12px;
  display: flex;
  gap: 8px;
}

/* 模型卡片 */
.model-card {
  margin-top: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-preview {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: linear-gradient(135deg, var(--brand-500) 0%, var(--brand-600) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.model-info {
  flex: 1;
}

.model-name {
  font-weight: 500;
  color: var(--text-primary);
}

.model-format {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 输入区域 */
.input-area {
  padding: 16px;
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
}

.input-wrapper {
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-wrapper :deep(.el-textarea__inner) {
  border-radius: var(--radius-lg);
  resize: none;
  box-shadow: var(--shadow-sm);
}

.input-wrapper :deep(.el-button) {
  border-radius: 50%;
  width: 40px;
  height: 40px;
  padding: 0;
}

.input-hints {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.input-hints .el-tag {
  cursor: pointer;
  transition: all var(--transition-fast);
}

.input-hints .el-tag:hover {
  transform: translateY(-2px);
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 16px;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-tertiary);
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* 滚动条样式 */
.chat-container::-webkit-scrollbar {
  width: 6px;
}

.chat-container::-webkit-scrollbar-track {
  background: transparent;
}

.chat-container::-webkit-scrollbar-thumb {
  background: var(--bg-400);
  border-radius: 3px;
}

.chat-container::-webkit-scrollbar-thumb:hover {
  background: var(--bg-500);
}
</style>
