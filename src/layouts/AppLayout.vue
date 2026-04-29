<template>
  <div class="app-layout" :class="{ 'dark-theme': isDark }">
    <div class="sidebar-wrapper" :class="{ collapsed: sidebarCollapsed }">
      <Sidebar />
    </div>
    <div class="main-wrapper">
      <AppHeader />
      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import Sidebar from './Sidebar.vue'
import AppHeader from './AppHeader.vue'

const appStore = useAppStore()

const sidebarCollapsed = computed(() => appStore.sidebarCollapsed)
const isDark = computed(() => appStore.currentTheme === 'dark')

onMounted(() => {
  applyTheme()
})

watch(() => appStore.currentTheme, () => {
  applyTheme()
})

function applyTheme() {
  if (appStore.currentTheme === 'dark') {
    document.documentElement.classList.add('dark')
    document.body.style.backgroundColor = 'var(--lj-bg-dark)'
  } else {
    document.documentElement.classList.remove('dark')
    document.body.style.backgroundColor = 'var(--lj-bg)'
  }
}
</script>

<style scoped lang="scss">
.app-layout {
  display: flex;
  height: 100vh;
  width: 100%;
  transition: all 0.3s ease;
  
  &.dark-theme {
    .main-wrapper {
      .main-content {
        background-color: #0f1419;
      }
    }
  }
  
  .sidebar-wrapper {
    width: var(--lj-sidebar-width);
    height: 100%;
    overflow: hidden;
    transition: width 0.3s ease;
    
    &.collapsed {
      width: 64px;
    }
  }
  
  .main-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    
    .main-content {
      flex: 1;
      padding: 20px;
      overflow-y: auto;
      background-color: var(--lj-bg);
      transition: background-color 0.3s ease;
    }
  }
}

@media (max-width: 768px) {
  .app-layout {
    .sidebar-wrapper {
      position: fixed;
      left: 0;
      top: 0;
      z-index: 1000;
      transform: translateX(-100%);
      
      &.show {
        transform: translateX(0);
      }
    }
  }
}
</style>
