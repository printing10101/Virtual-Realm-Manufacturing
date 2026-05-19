<template>
  <div class="settings-page">
    <GeneralSettings />
    <AISettings />
    <ProcessSettings />
    <UISettings />
  </div>
</template>

<script setup lang="ts">
import GeneralSettings from '@/components/settings/GeneralSettings.vue'
import AISettings from '@/components/settings/AISettings.vue'
import ProcessSettings from '@/components/settings/ProcessSettings.vue'
import UISettings from '@/components/settings/UISettings.vue'
</script>

<style scoped>
.settings-page {
  max-width: 900px;
  margin: 0 auto;
}
</style>