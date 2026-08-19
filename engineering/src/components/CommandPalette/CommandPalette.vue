<template>
  <teleport to="body">
    <transition name="fade">
      <div
        v-if="state.visible"
        class="command-palette-overlay"
        @click.self="close"
      >
        <div
          class="command-palette"
          :style="{ maxWidth: isMobile ? '90vw' : '600px' }"
        >
          <!-- 搜索输入 -->
          <div class="palette-header">
            <el-icon class="search-icon">
              <Search />
            </el-icon>
            <input
              ref="inputRef"
              v-model="query"
              class="palette-input"
              :placeholder="t('commandPalette.inputPlaceholder')"
              @keydown="handleKeydown"
            >
            <kbd
              v-if="!isMobile"
              class="shortcut-hint"
            >ESC</kbd>
          </div>

          <!-- 命令列表 -->
          <div
            class="palette-body"
            @keydown="handleKeydown"
          >
            <div
              v-if="filteredCommands.length === 0"
              class="empty-state"
            >
              <el-icon><Warning /></el-icon>
              <p>{{ t('commandPalette.noMatchFound') }}</p>
            </div>

            <template v-else>
              <div
                v-for="(group, category) in groupedCommands"
                :key="category"
                class="command-group"
              >
                <div class="group-title">
                  {{ category }}
                </div>
                <div
                  v-for="(cmd, _index) in group"
                  :key="cmd.id"
                  :class="[
                    'command-item',
                    { 'command-item--selected': isSelected(cmd) }
                  ]"
                  @click="executeCommand(cmd)"
                  @mouseenter="selectCommand(cmd)"
                >
                  <div class="command-icon">
                    <el-icon v-if="cmd.icon">
                      <component :is="cmd.icon" />
                    </el-icon>
                    <el-icon v-else>
                      <Operation />
                    </el-icon>
                  </div>
                  <div class="command-content">
                    <div class="command-name">
                      {{ cmd.name }}
                    </div>
                    <div
                      v-if="cmd.description"
                      class="command-description"
                    >
                      {{ cmd.description }}
                    </div>
                  </div>
                  <div class="command-meta">
                    <kbd
                      v-if="cmd.shortcut"
                      class="command-shortcut"
                    >
                      {{ cmd.shortcut }}
                    </kbd>
                    <el-tag
                      v-if="usageData[cmd.id]?.count"
                      size="small"
                      type="info"
                      effect="plain"
                    >
                      {{ usageData[cmd.id].count }}
                    </el-tag>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- 底部提示 -->
          <div class="palette-footer">
            <div class="footer-hints">
              <span class="hint-item">
                <kbd>↑↓</kbd> {{ t('commandPalette.hintSelect') }}
              </span>
              <span class="hint-item">
                <kbd>↵</kbd> {{ t('commandPalette.hintExecute') }}
              </span>
              <span class="hint-item">
                <kbd>esc</kbd> {{ t('commandPalette.hintClose') }}
              </span>
            </div>
            <div class="footer-stats">
              {{ filteredCommands.length }} {{ t('commandPalette.commandCount') }}
            </div>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { Search, Warning, Operation } from '@element-plus/icons-vue'
import type { Command } from '@/composables/useCommandPalette'
import { useExtensionRegistry } from '@/composables/useExtensionRegistry'

const { t } = useI18n()

// Props
const props = defineProps<{
  commands: Command[]
}>()

// Emits
const emit = defineEmits<{
  execute: [command: Command]
}>()

// 扩展点：合并插件通过 command_palette.command 贡献的命令
// 插件注册格式：handler 接收 { name, description, category }，返回 { result, close } 或 undefined
const { list } = useExtensionRegistry()
const extensionCommands = computed<Command[]>(() => {
  const contributions = list('command_palette.command')
  return contributions
    .filter((c) => c.handler_fn)
    .map((c) => {
      const meta = c.metadata ?? {}
      return {
        id: `plugin:${c.plugin_id}:${c.extension_point}`,
        name: (meta.title as string) || c.plugin_id,
        description: (meta.description as string) || '',
        category: (meta.category as string) || t('commandPalette.pluginCategory'),
        icon: (meta.icon as string) || undefined,
        action: async () => {
          await c.handler_fn?.({})
        },
      } satisfies Command
    })
})

// 合并后的完整命令列表（插件命令 + 本地命令）
const allCommands = computed<Command[]>(() => [...props.commands, ...extensionCommands.value])

// 状态
const inputRef = ref<HTMLInputElement | null>(null)
const query = ref('')
const selectedIndex = ref(0)
const isMobile = ref(false)

// 计算属性
const state = computed(() => ({
  visible: false,
  query: query.value,
  selectedIndex: selectedIndex.value
}))

const filteredCommands = computed(() => {
  const q = query.value.toLowerCase().trim()
  let result = allCommands.value.filter(cmd => !cmd.disabled)

  if (q) {
    result = result.filter(cmd => {
      const searchText = `${cmd.name} ${cmd.description || ''} ${cmd.category || ''}`.toLowerCase()
      return fuzzyMatch(searchText, q)
    })
  }

  // 按名称排序
  result.sort((a, b) => a.name.localeCompare(b.name))
  return result
})

const groupedCommands = computed(() => {
  const groups: Record<string, Command[]> = {}
  filteredCommands.value.forEach(cmd => {
    const category = cmd.category || t('commandPalette.otherCategory')
    if (!groups[category]) {
      groups[category] = []
    }
    groups[category].push(cmd)
  })
  return groups
})

const usageData = computed(() => {
  try {
    const raw = localStorage.getItem('command_palette_usage')
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
})

// 方法
function open() {
  state.value.visible = true
  query.value = ''
  selectedIndex.value = 0
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function close() {
  state.value.visible = false
  query.value = ''
  selectedIndex.value = 0
}

function toggle() {
  if (state.value.visible) {
    close()
  } else {
    open()
  }
}

function isSelected(cmd: Command): boolean {
  const flatList = filteredCommands.value
  const selectedCmd = flatList[selectedIndex.value]
  return selectedCmd?.id === cmd.id
}

function selectCommand(cmd: Command) {
  const index = filteredCommands.value.findIndex(c => c.id === cmd.id)
  if (index >= 0) {
    selectedIndex.value = index
  }
}

function executeCommand(cmd: Command) {
  emit('execute', cmd)
  cmd.action()
  close()
}

function handleKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      if (selectedIndex.value < filteredCommands.value.length - 1) {
        selectedIndex.value++
      }
      break
    case 'ArrowUp':
      event.preventDefault()
      if (selectedIndex.value > 0) {
        selectedIndex.value--
      }
      break
    case 'Enter': {
      event.preventDefault()
      const cmd = filteredCommands.value[selectedIndex.value]
      if (cmd) {
        executeCommand(cmd)
      }
      break
    }
    case 'Escape':
      event.preventDefault()
      close()
      break
  }
}

function fuzzyMatch(text: string, query: string): boolean {
  let queryIndex = 0
  let textIndex = 0

  while (queryIndex < query.length && textIndex < text.length) {
    if (query[queryIndex] === text[textIndex]) {
      queryIndex++
    }
    textIndex++
  }

  return queryIndex === query.length
}

// 监听窗口大小
function checkMobile() {
  isMobile.value = window.innerWidth < 768
}

// 生命周期
onMounted(() => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkMobile)
})

// 暴露方法
defineExpose({
  open,
  close,
  toggle
})
</script>

<style scoped lang="scss">
.command-palette-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--bg-overlay);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 15vh;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

.command-palette {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 70vh;
  animation: slideDown 0.2s ease;
}

.palette-header {
  display: flex;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-medium);
  background: var(--bg-secondary);

  .search-icon {
    font-size: 20px;
    color: var(--text-tertiary);
    margin-right: 12px;
  }

  .palette-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 16px;
    background: transparent;

    &::placeholder {
      color: var(--text-tertiary);
    }
  }

  .shortcut-hint {
    background: var(--border-medium);
    padding: 4px 8px;
    border-radius: var(--radius-xs);
    font-size: 12px;
    color: var(--text-secondary);
  }
}

.palette-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 20px;
    color: var(--text-tertiary);

    .el-icon {
      font-size: 48px;
      margin-bottom: 12px;
    }

    p {
      margin: 0;
      font-size: 14px;
    }
  }

  .command-group {
    .group-title {
      padding: 8px 20px 4px;
      font-size: 12px;
      font-weight: 600;
      color: var(--text-tertiary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .command-item {
      display: flex;
      align-items: center;
      padding: 12px 20px;
      cursor: pointer;
      transition: background-color 0.15s;

      &:hover,
      &--selected {
        background-color: var(--bg-tertiary);
      }

      &--selected {
        background-color: var(--bg-secondary);
      }

      .command-icon {
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 12px;
        color: var(--accent-primary);
        font-size: 18px;
      }

      .command-content {
        flex: 1;
        min-width: 0;

        .command-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--text-primary);
          margin-bottom: 2px;
        }

        .command-description {
          font-size: 12px;
          color: var(--text-tertiary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }

      .command-meta {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-left: 12px;

        .command-shortcut {
          background: var(--border-medium);
          padding: 2px 6px;
          border-radius: var(--radius-2xs);
          font-size: 11px;
          color: var(--text-secondary);
          font-family: var(--font-mono);
        }
      }
    }
  }
}

.palette-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-top: 1px solid var(--border-medium);
  background: var(--bg-secondary);
  font-size: 12px;

  .footer-hints {
    display: flex;
    gap: 16px;

    .hint-item {
      display: flex;
      align-items: center;
      gap: 4px;
      color: var(--text-tertiary);

      kbd {
        background: var(--border-medium);
        padding: 2px 6px;
        border-radius: var(--radius-2xs);
        font-size: 11px;
        color: var(--text-secondary);
        font-family: var(--font-mono);
      }
    }
  }

  .footer-stats {
    color: var(--text-tertiary);
  }
}

// 动画
@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes slideDown {
  from {
    transform: translateY(-20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

// 响应式
@media (max-width: 768px) {
  .command-palette-overlay {
    padding-top: 10vh;
  }

  .command-palette {
    max-height: 80vh;
  }

  .palette-footer {
    .footer-hints {
      display: none;
    }
  }
}
</style>
