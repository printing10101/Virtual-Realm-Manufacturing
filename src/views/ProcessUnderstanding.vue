<template>
  <div class="process-understanding">
    <!-- 顶部标题栏 -->
    <header class="pu-header">
      <div class="pu-title">
        <h1>{{ t('processUnderstanding.pageTitle') }}</h1>
        <span class="pu-subtitle">{{ t('processUnderstanding.pageSubtitle') }}</span>
      </div>
      <div class="pu-status">
        <el-tag
          :type="store.isHealthy ? 'success' : 'danger'"
          effect="light"
          size="small"
        >
          <el-icon><component :is="store.isHealthy ? CircleCheck : CircleClose" /></el-icon>
          {{ store.isHealthy ? t('processUnderstanding.statusHealthy') : t('processUnderstanding.statusUnavailable') }}
        </el-tag>
        <el-button
          text
          size="small"
          :disabled="!store.hasHistory || store.loading"
          @click="store.clearHistory()"
        >
          <el-icon><Delete /></el-icon>
          {{ t('processUnderstanding.btnClearHistory') }}
        </el-button>
      </div>
    </header>

    <!-- 对话区域 -->
    <main
      ref="conversationRef"
      class="pu-conversation"
    >
      <!-- 空状态 -->
      <div
        v-if="!store.hasHistory"
        class="pu-empty"
      >
        <el-icon
          :size="48"
          color="var(--text-secondary)"
        >
          <ChatDotRound />
        </el-icon>
        <h2>{{ t('processUnderstanding.emptyTitle') }}</h2>
        <p>{{ t('processUnderstanding.emptyHint') }}</p>
        <div class="pu-suggestions">
          <el-button
            v-for="s in suggestions"
            :key="s"
            text
            @click="quickAsk(s)"
          >
            {{ s }}
          </el-button>
        </div>
      </div>

      <!-- 消息列表 -->
      <div
        v-else
        class="pu-messages"
      >
        <div
          v-for="msg in store.messages"
          :key="msg.id"
          :class="['pu-message', `pu-message-${msg.role}`]"
        >
          <div class="pu-message-avatar">
            <el-icon :size="20">
              <component :is="msg.role === 'user' ? User : Cpu" />
            </el-icon>
          </div>
          <div class="pu-message-body">
            <!-- 用户消息 -->
            <div
              v-if="msg.role === 'user'"
              class="pu-message-content"
            >
              {{ msg.content }}
            </div>

            <!-- 助手消息 -->
            <template v-else>
              <div class="pu-message-content">
                {{ msg.content }}
              </div>

              <!-- 结构化结果展示 -->
              <div
                v-if="msg.result"
                class="pu-result"
              >
                <!-- 任务类型 + 置信度 -->
                <div class="pu-result-meta">
                  <el-tag
                    size="small"
                    type="info"
                  >
                    {{ taskTypeLabel(msg.result.task_type) }}
                  </el-tag>
                  <el-tag
                    size="small"
                    type="primary"
                  >
                    {{ msg.result.intent }}
                  </el-tag>
                  <div class="pu-confidence">
                    <span class="pu-confidence-label">{{ t('processUnderstanding.confidenceLabel') }}</span>
                    <el-progress
                      :percentage="Math.round(msg.result.confidence * 100)"
                      :stroke-width="6"
                      :status="confidenceStatus(msg.result.confidence)"
                      style="width: 120px"
                    />
                  </div>
                </div>

                <!-- 实体识别 -->
                <div
                  v-if="Object.keys(msg.result.entities).length > 0"
                  class="pu-entities"
                >
                  <span class="pu-section-label">{{ t('processUnderstanding.sectionEntities') }}</span>
                  <div class="pu-entity-tags">
                    <el-tag
                      v-for="(val, key) in msg.result.entities"
                      :key="key"
                      size="small"
                      effect="plain"
                    >
                      {{ key }}: {{ val }}
                    </el-tag>
                  </div>
                </div>

                <!-- 来源 -->
                <div
                  v-if="msg.result.sources.length > 0"
                  class="pu-sources"
                >
                  <span class="pu-section-label">{{ t('processUnderstanding.sectionSources') }}</span>
                  <ul class="pu-source-list">
                    <!-- 动态字符串列表，无业务唯一 id，index 作为 key 可接受 -->
                    <li
                      v-for="(src, i) in msg.result.sources"
                      :key="i"
                    >
                      {{ src }}
                    </li>
                  </ul>
                </div>

                <!-- 建议动作 -->
                <div
                  v-if="msg.result.actions.length > 0"
                  class="pu-actions"
                >
                  <span class="pu-section-label">{{ t('processUnderstanding.sectionActions') }}</span>
                  <ul class="pu-action-list">
                    <!-- 动态字符串列表，无业务唯一 id，index 作为 key 可接受 -->
                    <li
                      v-for="(act, i) in msg.result.actions"
                      :key="i"
                    >
                      {{ act }}
                    </li>
                  </ul>
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- 加载指示器 -->
        <div
          v-if="store.loading"
          class="pu-loading"
        >
          <el-icon class="pu-loading-icon">
            <Loading />
          </el-icon>
          <span>{{ t('processUnderstanding.loadingThinking') }}</span>
        </div>
      </div>
    </main>

    <!-- 底部输入区 -->
    <footer class="pu-input-area">
      <el-input
        v-model="inputText"
        type="textarea"
        :rows="2"
        :placeholder="t('processUnderstanding.inputPlaceholder')"
        resize="none"
        :disabled="store.loading"
        @keydown.enter.exact.prevent="send"
      />
      <el-button
        type="primary"
        :loading="store.loading"
        :disabled="!inputText.trim()"
        @click="send"
      >
        <el-icon><Promotion /></el-icon>
        {{ t('processUnderstanding.btnSend') }}
      </el-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import {
  ChatDotRound, User, Cpu, Delete, Promotion,
  CircleCheck, CircleClose, Loading,
} from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { useProcessUnderstandingStore } from '@/stores/processUnderstanding'

const { t } = useI18n()
const store = useProcessUnderstandingStore()

const inputText = ref('')
const conversationRef = ref<HTMLElement | null>(null)

/** 示例问题 */
const suggestions = computed(() => [
  t('processUnderstanding.suggestionMilling'),
  t('processUnderstanding.suggestionToolWear'),
  t('processUnderstanding.suggestionRoughing'),
  t('processUnderstanding.suggestionChatter'),
])

/** 任务类型标签 */
function taskTypeLabel(type: string): string {
  const map: Record<string, string> = {
    'A': t('processUnderstanding.taskTypeConsulting'),
    'B': t('processUnderstanding.taskTypeDiagnosis'),
    'C': t('processUnderstanding.taskTypeSolution'),
    'D': t('processUnderstanding.taskTypeKnowledge'),
    'E': t('processUnderstanding.taskTypeChat'),
  }
  // 支持完整格式 "A-工艺咨询" 或简写 "A"
  const key = type.split('-')[0]
  return map[key] || type || t('processUnderstanding.taskTypeUnknown')
}

/** 置信度状态 */
function confidenceStatus(c: number): 'success' | 'warning' | 'exception' {
  if (c >= 0.7) return 'success'
  if (c >= 0.4) return 'warning'
  return 'exception'
}

/** 发送消息 */
async function send(): Promise<void> {
  const text = inputText.value.trim()
  if (!text || store.loading) return
  inputText.value = ''
  await store.sendQuery(text)
  await scrollToBottom()
}

/** 快速提问 */
async function quickAsk(q: string): Promise<void> {
  if (store.loading) return
  await store.sendQuery(q)
  await scrollToBottom()
}

/** 滚动到底部 */
async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (conversationRef.value) {
    conversationRef.value.scrollTop = conversationRef.value.scrollHeight
  }
}

onMounted(() => {
  store.refreshHealth()
})
</script>

<style scoped>
.process-understanding {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--bg-secondary, #f5f7fa);
}

/* 顶部标题栏 */
.pu-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: var(--bg-primary, #fff);
  border-bottom: 1px solid var(--border-lighter, #e4e7ed);
  flex-shrink: 0;
}

.pu-title h1 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary, #303133);
}

.pu-subtitle {
  font-size: 12px;
  color: var(--text-secondary, #909399);
  margin-left: 8px;
}

.pu-status {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 对话区域 */
.pu-conversation {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  min-height: 0;
}

/* 空状态 */
.pu-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--text-secondary, #909399);
}

.pu-empty h2 {
  margin: 16px 0 8px;
  font-size: 16px;
  color: var(--text-primary, #303133);
}

.pu-suggestions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 16px;
}

/* 消息列表 */
.pu-messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 900px;
  margin: 0 auto;
}

.pu-message {
  display: flex;
  gap: 12px;
}

.pu-message-user {
  flex-direction: row-reverse;
}

.pu-message-avatar {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary, #f0f2f5);
  color: var(--text-secondary, #909399);
}

.pu-message-user .pu-message-avatar {
  background: var(--accent-primary, #409eff);
  color: #fff;
}

.pu-message-body {
  flex: 1;
  min-width: 0;
  max-width: calc(100% - 48px);
}

.pu-message-content {
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-lighter, #e4e7ed);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.pu-message-user .pu-message-content {
  background: var(--accent-primary, #409eff);
  color: #fff;
  border-color: var(--accent-primary, #409eff);
}

/* 结构化结果 */
.pu-result {
  margin-top: 8px;
  padding: 12px 16px;
  background: var(--bg-primary, #fff);
  border: 1px solid var(--border-lighter, #e4e7ed);
  border-radius: 8px;
  font-size: 13px;
}

.pu-result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border-lighter, #e4e7ed);
}

.pu-confidence {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.pu-confidence-label {
  font-size: 12px;
  color: var(--text-secondary, #909399);
}

.pu-section-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary, #909399);
  margin-bottom: 6px;
  font-weight: 500;
}

.pu-entities,
.pu-sources,
.pu-actions {
  margin-top: 8px;
}

.pu-entity-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pu-source-list,
.pu-action-list {
  margin: 0;
  padding-left: 20px;
  color: var(--text-regular, #606266);
  line-height: 1.8;
}

.pu-action-list li {
  color: var(--accent-primary, #409eff);
}

/* 加载指示器 */
.pu-loading {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  padding: 16px;
  color: var(--text-secondary, #909399);
  font-size: 13px;
}

.pu-loading-icon {
  animation: pu-spin 1s linear infinite;
}

@keyframes pu-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 底部输入区 */
.pu-input-area {
  display: flex;
  gap: 12px;
  padding: 16px 24px;
  background: var(--bg-primary, #fff);
  border-top: 1px solid var(--border-lighter, #e4e7ed);
  flex-shrink: 0;
  max-width: 900px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
}

.pu-input-area :deep(.el-textarea__inner) {
  resize: none;
}
</style>
