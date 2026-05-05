<template>
  <el-menu
    :default-active="activeMenu"
    class="sidebar-menu"
    :class="{ 'is-collapsed': collapsed }"
    :collapse="collapsed"
    background-color="#304156"
    text-color="#bfcbd9"
    active-text-color="#409EFF"
    router
  >
    <div class="logo-container">
      <h2
        v-if="!collapsed"
        class="logo-text"
      >
        灵境制造
      </h2>
      <span
        v-else
        class="logo-icon"
      >LJ</span>
    </div>
    
    <el-menu-item
      index="/home"
      @mouseenter="handleMenuHover('/home')"
    >
      <el-icon><HomeFilled /></el-icon>
      <template #title>
        {{ t('common.home') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/workspace"
      @mouseenter="handleMenuHover('/workspace')"
    >
      <el-icon><Monitor /></el-icon>
      <template #title>
        {{ t('common.workspace') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/multi-view-to-3d"
      @mouseenter="handleMenuHover('/multi-view-to-3d')"
    >
      <el-icon><Box /></el-icon>
      <template #title>
        {{ t('common.multiViewTo3D') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/process-plan"
      @mouseenter="handleMenuHover('/process-plan')"
    >
      <el-icon><Document /></el-icon>
      <template #title>
        {{ t('common.processPlan') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/validation"
      @mouseenter="handleMenuHover('/validation')"
    >
      <el-icon><DataAnalysis /></el-icon>
      <template #title>
        仿真验证
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/experience"
      @mouseenter="handleMenuHover('/experience')"
    >
      <el-icon><Collection /></el-icon>
      <template #title>
        {{ t('common.experience') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/models"
      @mouseenter="handleMenuHover('/models')"
    >
      <el-icon><Cpu /></el-icon>
      <template #title>
        模型管理
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/comparison"
      @mouseenter="handleMenuHover('/comparison')"
    >
      <el-icon><DataBoard /></el-icon>
      <template #title>
        {{ t('common.comparison') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/settings"
      @mouseenter="handleMenuHover('/settings')"
    >
      <el-icon><Setting /></el-icon>
      <template #title>
        {{ t('common.settings') }}
      </template>
    </el-menu-item>
    
    <el-menu-item
      index="/about"
      @mouseenter="handleMenuHover('/about')"
    >
      <el-icon><InfoFilled /></el-icon>
      <template #title>
        {{ t('common.about') }}
      </template>
    </el-menu-item>
    
    <div
      class="collapse-btn"
      @click="toggleCollapse"
    >
      <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
    </div>
  </el-menu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { preloadRoute } from '@/router'
import {
  HomeFilled,
  Monitor,
  Box,
  Document,
  Setting,
  InfoFilled,
  Fold,
  Expand,
  DataAnalysis,
  Collection,
  Cpu,
  DataBoard
} from '@element-plus/icons-vue'

const route = useRoute()
const { t } = useI18n()
const appStore = useAppStore()

const activeMenu = computed(() => route.path)
const collapsed = computed(() => appStore.sidebarCollapsed)

// 路由名称映射表
const routeNameMap: Record<string, string> = {
  '/home': 'Home',
  '/workspace': 'Workspace',
  '/multi-view-to-3d': 'MultiViewTo3D',
  '/process-plan': 'ProcessPlan',
  '/validation': 'Validation',
  '/experience': 'Experience',
  '/models': 'Models',
  '/comparison': 'Comparison',
  '/settings': 'Settings',
  '/about': 'About',
}

// 鼠标悬停时预加载
function handleMenuHover(path: string) {
  const routeName = routeNameMap[path]
  if (routeName) {
    preloadRoute(routeName)
  }
}

function toggleCollapse() {
  appStore.toggleSidebar()
}
</script>

<style scoped lang="scss">
.sidebar-menu {
  height: 100%;
  border-right: none;
  position: relative;
  
  &.is-collapsed {
    .logo-container {
      padding: 0;
    }
  }
}

.logo-container {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #263445;
  
  .logo-text {
    color: #fff;
    font-size: 20px;
    font-weight: bold;
    margin: 0;
    white-space: nowrap;
  }
  
  .logo-icon {
    color: #fff;
    font-size: 18px;
    font-weight: bold;
  }
}

.collapse-btn {
  position: absolute;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #bfcbd9;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.1);
  transition: all 0.3s;
  
  &:hover {
    background-color: rgba(255, 255, 255, 0.2);
    color: #fff;
  }
  
  .el-icon {
    font-size: 20px;
  }
}
</style>
