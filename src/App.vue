<template>
  <el-config-provider :locale="elLocale">
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
              {{ $t('navigation.home') }}
            </el-menu-item>
            <el-menu-item index="/workspace">
              {{ $t('navigation.workspace') }}
            </el-menu-item>
            <el-menu-item index="/settings">
              {{ $t('navigation.settings') }}
            </el-menu-item>
            <el-menu-item index="/about">
              {{ $t('navigation.about') }}
            </el-menu-item>
          </el-menu>
        </el-header>
        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, inject, ref, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useVersionStore } from '@/stores/version'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'

const title = '灵境制造 V4'
const route = useRoute()
const activeRoute = computed(() => route.path)

const elLocaleRef = inject<Ref<typeof zhCn>>('locale', ref(zhCn))
const elLocale = computed(() => elLocaleRef.value)

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
