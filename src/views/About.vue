<template>
  <div class="about-view">
    <el-card class="about-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('about.title') }}</h2>
        </div>
      </template>
      
      <div class="about-content">
        <div class="logo-section">
          <div class="logo-icon">
            <el-icon :size="64" color="#409eff"><Monitor /></el-icon>
          </div>
          <h3>灵境制造 V4</h3>
          <p class="subtitle">{{ t('about.subtitle') }}</p>
        </div>
        
        <el-divider />
        
        <div class="info-section">
          <h4>{{ t('about.versionInfo') }}</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item :label="t('about.version')">{{ version }}</el-descriptions-item>
            <el-descriptions-item :label="t('about.buildTime')">{{ buildTime }}</el-descriptions-item>
            <el-descriptions-item :label="t('about.techStack')">{{ t('about.techStackValue') }}</el-descriptions-item>
          </el-descriptions>
        </div>
        
        <el-divider />
        
        <div class="info-section">
          <h4>{{ t('about.coreFeatures') }}</h4>
          <el-row :gutter="16">
            <el-col :xs="24" :sm="12" v-for="feature in features" :key="feature.key">
              <div class="feature-item">
                <el-icon :size="24" :color="feature.color"><component :is="feature.icon" /></el-icon>
                <span>{{ t(feature.key) }}</span>
              </div>
            </el-col>
          </el-row>
        </div>
        
        <el-divider />
        
        <div class="info-section">
          <h4>{{ t('about.contact') }}</h4>
          <el-descriptions :column="1" border>
            <el-descriptions-item :label="t('about.github')"><a href="https://github.com" target="_blank" class="link">GitHub</a></el-descriptions-item>
            <el-descriptions-item :label="t('about.license')">{{ t('about.licenseValue') }}</el-descriptions-item>
          </el-descriptions>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { Monitor, Box, Document, Cpu, Tools } from '@element-plus/icons-vue'

const { t } = useI18n()

const version = '0.1.0'
const buildTime = '2026-04-29'

const features = [
  { key: 'about.feature1', icon: Box, color: '#409eff' },
  { key: 'about.feature2', icon: Document, color: '#67c23a' },
  { key: 'about.feature3', icon: Cpu, color: '#e6a23c' },
  { key: 'about.feature4', icon: Tools, color: '#f56c6c' }
]
</script>

<style scoped lang="scss">
.about-view {
  .about-card {
    max-width: 800px;
    margin: 0 auto;
    
    .card-header {
      h2 {
        margin: 0;
        font-size: 20px;
        color: #303133;
      }
    }
  }
  
  .about-content {
    .logo-section {
      text-align: center;
      padding: 20px 0;
      
      .logo-icon {
        width: 100px;
        height: 100px;
        margin: 0 auto 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #ecf5ff 0%, #d9ecff 100%);
        border-radius: 50%;
      }
      
      h3 {
        margin: 0 0 8px;
        font-size: 24px;
        color: #303133;
      }
      
      .subtitle {
        margin: 0;
        font-size: 14px;
        color: #909399;
      }
    }
    
    .info-section {
      h4 {
        margin: 0 0 16px;
        font-size: 16px;
        color: #303133;
      }
      
      .feature-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 12px 16px;
        background-color: #f5f7fa;
        border-radius: var(--lj-module-radius);
        margin-bottom: 12px;
        
        span {
          font-size: 14px;
          color: #303133;
        }
      }
    }
    
    .link {
      color: #409eff;
      text-decoration: none;
      
      &:hover {
        text-decoration: underline;
      }
    }
  }
}

@media (max-width: 768px) {
  .about-view {
    .about-card {
      .about-content {
        .info-section {
          .feature-item {
            padding: 10px 12px;
          }
        }
      }
    }
  }
}
</style>
