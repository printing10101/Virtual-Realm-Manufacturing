<template>
  <div id="app">
    <el-container class="app-container">
      <el-header class="app-header">
        <div class="header-left">
          <h1 class="app-title">
            {{ title }}
          </h1>
          <span class="app-version">v{{ frontendVersion }}</span>
        </div>
        <el-menu
          :default-active="activeRoute"
          mode="horizontal"
          router
          class="header-menu"
        >
          <el-menu-item index="/">
            首页
          </el-menu-item>
          <el-menu-item index="/workspace">
            工作区
          </el-menu-item>
          <el-menu-item index="/settings">
            设置
          </el-menu-item>
          <el-menu-item index="/about">
            关于
          </el-menu-item>
        </el-menu>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useVersionStore } from '@/stores/version'

const title = '灵境制造 V4'
const route = useRoute()
const activeRoute = computed(() => route.path)

const versionStore = useVersionStore()
const frontendVersion = computed(() => versionStore.frontendVersion)

onMounted(async () => {
  await versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
})
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
}

.app-title {
  margin: 0;
  font-size: 1.25rem;
  white-space: nowrap;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.app-version {
  font-size: 0.75rem;
  color: #909399;
  white-space: nowrap;
}

.header-menu {
  border-bottom: none;
}

.app-main {
  padding: 24px;
}
</style>
