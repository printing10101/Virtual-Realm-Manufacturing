<template>
  <header class="app-header" :class="{ 'dark-theme': isDark }">
    <div class="header-left">
      <el-icon class="menu-icon" @click="toggleSidebar" v-if="isMobile"><Fold /></el-icon>
      <span class="page-title">{{ currentRouteTitle }}</span>
    </div>
    <div class="header-right">
      <el-tooltip content="任务面板" placement="bottom">
        <div class="action-item task-panel-toggle" @click="toggleTaskPanel">
          <el-icon><Tickets /></el-icon>
          <span v-if="runningTaskCount > 0" class="task-badge">{{ runningTaskCount }}</span>
        </div>
      </el-tooltip>
      
      <el-dropdown @command="handleLanguageChange">
        <span class="action-item">
          <el-icon><Translate /></el-icon>
          <span>{{ currentLanguage === 'zh-CN' ? '中文' : 'EN' }}</span>
          <el-icon class="el-icon--right"><arrow-down /></el-icon>
        </span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="zh-CN">中文</el-dropdown-item>
            <el-dropdown-item command="en-US">English</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      
      <el-tooltip :content="isDark ? '切换浅色模式' : '切换深色模式'" placement="bottom">
        <div class="action-item theme-switch" @click="toggleTheme">
          <el-icon><Moon v-if="!isDark" /><Sunny v-else /></el-icon>
        </div>
      </el-tooltip>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowDown, Moon, Sunny, Fold, Connection as Translate, Tickets } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useSettingsStore } from '@/stores/settingsStore'
import { useTaskList } from '@/services/taskService'

const route = useRoute()
const { locale, t } = useI18n()
const appStore = useAppStore()
const settingsStore = useSettingsStore()
const { tasks } = useTaskList()

const currentRouteTitle = computed(() => route.meta.title as string || '')
const currentLanguage = computed(() => settingsStore.settings.language)
const isDark = computed(() => settingsStore.settings.theme === 'dark')
const isMobile = ref(false)

const runningTaskCount = computed(() => {
  return tasks.value.filter(t => t.status === 'running').length
})

const handleLanguageChange = (lang: string) => {
  locale.value = lang
  settingsStore.updateSetting('language', lang)
}

const toggleTheme = () => {
  settingsStore.updateSetting('theme', isDark.value ? 'light' : 'dark')
}

const toggleSidebar = () => {
  appStore.toggleSidebar()
}

const toggleTaskPanel = () => {
  appStore.toggleTaskPanel()
}
</script>

<style scoped lang="scss">
.app-header {
  height: var(--lj-header-height);
  padding: 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  transition: all 0.3s ease;
  
  &.dark-theme {
    background-color: #1a1a2e;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    
    .header-left {
      .page-title {
        color: #e0e0e0;
      }
    }
    
    .header-right {
      .action-item {
        color: #bfcbd9;
        
        &:hover {
          color: #fff;
          background-color: rgba(255, 255, 255, 0.1);
        }
      }
    }
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
    
    .menu-icon {
      cursor: pointer;
      font-size: 20px;
      color: #606266;
      
      &:hover {
        color: var(--lj-primary);
      }
    }
    
    .page-title {
      font-size: 18px;
      font-weight: 600;
      color: #303133;
    }
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .action-item {
      display: flex;
      align-items: center;
      cursor: pointer;
      color: #606266;
      padding: 6px 12px;
      border-radius: 6px;
      transition: all 0.3s;
      font-size: 14px;
      
      &:hover {
        color: var(--lj-primary);
        background-color: rgba(64, 158, 255, 0.1);
      }
      
      &.theme-switch {
        padding: 8px;
        
        .el-icon {
          font-size: 18px;
        }
      }
      
      &.task-panel-toggle {
        position: relative;
        padding: 8px;
        
        .task-badge {
          position: absolute;
          top: 2px;
          right: 2px;
          min-width: 16px;
          height: 16px;
          padding: 0 4px;
          background: #ff4d4f;
          color: #fff;
          font-size: 10px;
          line-height: 16px;
          text-align: center;
          border-radius: 8px;
          transform: scale(0.8);
        }
      }
    }
  }
}
</style>
