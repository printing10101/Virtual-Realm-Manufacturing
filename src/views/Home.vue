<template>
  <div class="home-page">
    <el-row :gutter="24">
      <el-col :span="16">
        <el-card class="welcome-card">
          <h2>{{ $t('home.welcome') }}</h2>
          <p>{{ $t('home.welcomeDesc') }}</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            {{ $t('home.systemStatus') }}
          </template>
          <div class="status-item">
            <span>{{ $t('home.aiService') }}</span>
            <el-tag type="success">
              {{ $t('home.running') }}
            </el-tag>
          </div>
          <div class="status-item">
            <span>{{ $t('home.registeredModels') }}</span>
            <span class="stat-value">4</span>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-card h2 {
  margin: 0 0 12px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-value {
  font-weight: bold;
  color: #409eff;
}
</style>
