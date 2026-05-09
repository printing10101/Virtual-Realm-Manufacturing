<template>
  <div class="home-page">
    <el-row :gutter="24">
      <el-col :span="16">
        <el-card class="welcome-card">
          <h2>欢迎使用灵境制造 V4</h2>
          <p>AI驱动的智能制造平台，提供工具磨损预测、工艺参数优化与3D可视化功能</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>系统状态</template>
          <div class="status-item">
            <span>AI服务</span>
            <el-tag type="success">运行中</el-tag>
          </div>
          <div class="status-item">
            <span>模型注册数</span>
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
