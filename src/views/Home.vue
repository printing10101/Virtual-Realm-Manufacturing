<template>
  <div class="home-view">
    <el-card class="welcome-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <div class="header-content">
            <h1>{{ t('home.welcome') }}</h1>
            <p class="subtitle">{{ t('home.subtitle') }}</p>
          </div>
          <div class="header-actions">
            <el-button type="primary" size="large" @click="navigateTo('/workspace')">
              <el-icon><Monitor /></el-icon>
              {{ t('home.startNow') }}
            </el-button>
          </div>
        </div>
      </template>
      
      <p class="description">{{ t('home.description') }}</p>
      
      <div class="features-grid">
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="feature-card card-hover" @click="navigateTo('/multi-view-to-3d')">
              <div class="feature-icon icon-3d">
                <el-icon size="48"><Box /></el-icon>
              </div>
              <h3>{{ t('home.feature3d.title') }}</h3>
              <p>{{ t('home.feature3d.desc') }}</p>
              <el-button text type="primary" class="link-btn">
                {{ t('home.tryNow') }} <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="feature-card card-hover" @click="navigateTo('/process-plan')">
              <div class="feature-icon icon-process">
                <el-icon size="48"><Document /></el-icon>
              </div>
              <h3>{{ t('home.featureProcess.title') }}</h3>
              <p>{{ t('home.featureProcess.desc') }}</p>
              <el-button text type="primary" class="link-btn">
                {{ t('home.tryNow') }} <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="feature-card card-hover" @click="navigateTo('/workspace')">
              <div class="feature-icon icon-workspace">
                <el-icon size="48"><Monitor /></el-icon>
              </div>
              <h3>{{ t('home.featureWorkspace.title') }}</h3>
              <p>{{ t('home.featureWorkspace.desc') }}</p>
              <el-button text type="primary" class="link-btn">
                {{ t('home.tryNow') }} <el-icon><ArrowRight /></el-icon>
              </el-button>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <el-divider />

      <div class="quick-stats">
        <h3 class="section-title">{{ t('home.quickStart') }}</h3>
        <el-row :gutter="20">
          <el-col :xs="24" :sm="12" :md="6" v-for="item in quickLinks" :key="item.path">
            <div class="stat-item" @click="navigateTo(item.path)">
              <el-icon :size="32" :color="item.color"><component :is="item.icon" /></el-icon>
              <span>{{ item.label }}</span>
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { Box, Document, Monitor, Setting, InfoFilled, ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()
const { t } = useI18n()

const quickLinks = [
  { path: '/multi-view-to-3d', label: t('common.multiViewTo3D'), icon: Box, color: '#409eff' },
  { path: '/process-plan', label: t('common.processPlan'), icon: Document, color: '#67c23a' },
  { path: '/settings', label: t('common.settings'), icon: Setting, color: '#e6a23c' },
  { path: '/about', label: t('common.about'), icon: InfoFilled, color: '#909399' }
]

function navigateTo(path: string) {
  router.push(path)
}
</script>

<style scoped lang="scss">
.home-view {
  .welcome-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .header-content {
        h1 {
          margin: 0 0 8px;
          font-size: 28px;
          color: #303133;
        }
        
        .subtitle {
          margin: 0;
          font-size: 16px;
          color: #909399;
        }
      }
    }
    
    .description {
      font-size: 15px;
      color: #606266;
      margin-bottom: 30px;
      line-height: 1.6;
    }
    
    .features-grid {
      .feature-card {
        text-align: center;
        padding: 30px 20px;
        cursor: pointer;
        border: none;
        
        .feature-icon {
          width: 80px;
          height: 80px;
          margin: 0 auto 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          
          &.icon-3d {
            background: linear-gradient(135deg, #409eff 0%, #79bbff 100%);
            color: #fff;
          }
          
          &.icon-process {
            background: linear-gradient(135deg, #67c23a 0%, #b3e19d 100%);
            color: #fff;
          }
          
          &.icon-workspace {
            background: linear-gradient(135deg, #e6a23c 0%, #f3d19e 100%);
            color: #fff;
          }
        }
        
        h3 {
          margin: 0 0 10px;
          font-size: 18px;
          color: #303133;
        }
        
        p {
          color: #909399;
          font-size: 14px;
          margin-bottom: 16px;
        }
        
        .link-btn {
          font-size: 14px;
        }
      }
    }
    
    .quick-stats {
      .section-title {
        margin-bottom: 20px;
        font-size: 18px;
        color: #303133;
      }
      
      .stat-item {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 16px 20px;
        background-color: #f5f7fa;
        border-radius: var(--lj-module-radius);
        cursor: pointer;
        transition: all 0.3s;
        margin-bottom: 12px;
        
        &:hover {
          background-color: #ecf5ff;
          transform: translateX(4px);
        }
        
        span {
          font-size: 15px;
          color: #303133;
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .home-view {
    .welcome-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 16px;
      }
    }
  }
}
</style>
