<template>
  <div class="ui-settings">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.agentTokenManage') }}</span>
        </div>
      </template>

      <el-alert
        :title="$t('settings.agentTokenInfo') || 'Agent Token 管理'"
        type="info"
        :closable="false"
        show-icon
      >
        <div>
          <p>{{ $t('settings.agentTokenDisabled') || '当前版本已简化为免登录模式，Agent Token 管理功能已移除。' }}</p>
          <p>{{ $t('settings.contactAdmin') || '如需访问控制功能，请联系管理员。' }}</p>
        </div>
      </el-alert>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// Agent Token 管理已移除 - 应用已简化为免登录模式
</script>

<style scoped>
.ui-settings {
  padding: 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
