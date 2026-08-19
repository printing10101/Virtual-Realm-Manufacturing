<template>
  <div class="ux-demo">
    <el-card class="demo-section">
      <template #header>
        <div class="card-header">
          <h3>{{ t('uxDemo.pageTitle') }}</h3>
          <div class="header-actions">
            <el-button
              type="primary"
              @click="startTour"
            >
              <el-icon><Guide /></el-icon>
              {{ t('uxDemo.btnStartTour') }}
            </el-button>
            <el-button @click="openCommandPalette">
              <el-icon><Search /></el-icon>
              {{ t('uxDemo.btnCommandPalette') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8">
          <el-statistic
            :title="t('uxDemo.statTourSteps')"
            :value="tourSteps.length"
          />
        </el-col>
        <el-col :span="8">
          <el-statistic
            :title="t('uxDemo.statExampleCount')"
            :value="exampleCount"
          />
        </el-col>
        <el-col :span="8">
          <el-statistic
            :title="t('uxDemo.statCommandCount')"
            :value="commandCount"
          />
        </el-col>
      </el-row>

      <el-divider />

      <div class="feature-list">
        <h4>{{ t('uxDemo.sectionFeatures') }}</h4>
        <el-descriptions
          :column="1"
          border
        >
          <el-descriptions-item :label="t('uxDemo.featureTourLabel')">
            <el-tag type="success">
              {{ t('uxDemo.tagCompleted') }}
            </el-tag>
            <span class="feature-desc">{{ t('uxDemo.featureTourDesc') }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('uxDemo.featureGalleryLabel')">
            <el-tag type="success">
              {{ t('uxDemo.tagCompleted') }}
            </el-tag>
            <span class="feature-desc">{{ t('uxDemo.featureGalleryDesc') }}</span>
          </el-descriptions-item>
          <el-descriptions-item :label="t('uxDemo.featureCommandLabel')">
            <el-tag type="success">
              {{ t('uxDemo.tagCompleted') }}
            </el-tag>
            <span class="feature-desc">{{ t('uxDemo.featureCommandDesc') }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-card>

    <!-- 引导流程组件 -->
    <Tour
      ref="tourRef"
      :steps="tourSteps"
      storage-key="ux-demo-tour"
      @start="onTourStart"
      @step-change="onTourStepChange"
      @finish="onTourFinish"
      @skip="onTourSkip"
    />

    <!-- 命令面板组件 -->
    <CommandPalette
      ref="commandPaletteRef"
      :commands="registeredCommands"
      @execute="onCommandExecute"
    />

    <!-- 示例工程库 -->
    <el-card class="demo-section">
      <template #header>
        <h3>{{ t('uxDemo.sectionGalleryPreview') }}</h3>
      </template>
      <ExampleGallery />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'

const { t } = useI18n()
import { Guide, Search } from '@element-plus/icons-vue'
import Tour from '@/components/Onboarding/Tour.vue'
import type { TourStep } from '@/components/Onboarding/Tour.vue'
import CommandPalette from '@/components/CommandPalette/CommandPalette.vue'
import type { Command } from '@/types/command'
import ExampleGallery from '@/examples/ExampleGallery.vue'
import { exampleProjects } from '@/examples/data'

// 引导步骤配置
const tourSteps: TourStep[] = [
  {
    title: t('uxDemo.tourStep1Title'),
    description: t('uxDemo.tourStep1Desc'),
    target: '.app-header',
    placement: 'bottom'
  },
  {
    title: t('uxDemo.tourStep2Title'),
    description: t('uxDemo.tourStep2Desc'),
    target: '.header-right',
    placement: 'bottom'
  },
  {
    title: t('uxDemo.tourStep3Title'),
    description: t('uxDemo.tourStep3Desc'),
    target: '.header-menu',
    placement: 'bottom'
  },
  {
    title: t('uxDemo.tourStep4Title'),
    description: t('uxDemo.tourStep4Desc'),
    target: '.header-actions',
    placement: 'bottom'
  },
  {
    title: t('uxDemo.tourStep5Title'),
    description: t('uxDemo.tourStep5Desc')
  }
]

// 注册命令
const registeredCommands = computed<Command[]>(() => [
  {
    id: 'new-project',
    name: t('uxDemo.cmdNewProjectName'),
    description: t('uxDemo.cmdNewProjectDesc'),
    category: t('uxDemo.categoryFile'),
    icon: 'DocumentAdd',
    shortcut: 'Ctrl+N',
    action: () => {
      ElMessage.success(t('uxDemo.msgNewProjectTriggered'))
    }
  },
  {
    id: 'open-project',
    name: t('uxDemo.cmdOpenProjectName'),
    description: t('uxDemo.cmdOpenProjectDesc'),
    category: t('uxDemo.categoryFile'),
    icon: 'FolderOpened',
    shortcut: 'Ctrl+O',
    action: () => {
      ElMessage.success(t('uxDemo.msgOpenProjectTriggered'))
    }
  },
  {
    id: 'save-project',
    name: t('uxDemo.cmdSaveProjectName'),
    description: t('uxDemo.cmdSaveProjectDesc'),
    category: t('uxDemo.categoryFile'),
    icon: 'Download',
    shortcut: 'Ctrl+S',
    action: () => {
      ElMessage.success(t('uxDemo.msgSaveProjectTriggered'))
    }
  },
  {
    id: 'export-gcode',
    name: t('uxDemo.cmdExportGCodeName'),
    description: t('uxDemo.cmdExportGCodeDesc'),
    category: t('uxDemo.categoryToolpath'),
    icon: 'Document',
    action: () => {
      ElMessage.success(t('uxDemo.msgExportGCodeTriggered'))
    }
  },
  {
    id: 'start-simulation',
    name: t('uxDemo.cmdStartSimulationName'),
    description: t('uxDemo.cmdStartSimulationDesc'),
    category: t('uxDemo.categorySimulation'),
    icon: 'VideoPlay',
    action: () => {
      ElMessage.success(t('uxDemo.msgStartSimulationTriggered'))
    }
  },
  {
    id: 'ai-feature-recognition',
    name: t('uxDemo.cmdAiFeatureName'),
    description: t('uxDemo.cmdAiFeatureDesc'),
    category: t('uxDemo.categoryAI'),
    icon: 'MagicStick',
    action: () => {
      ElMessage.success(t('uxDemo.msgAiFeatureTriggered'))
    }
  },
  {
    id: 'view-examples',
    name: t('uxDemo.cmdViewExamplesName'),
    description: t('uxDemo.cmdViewExamplesDesc'),
    category: t('uxDemo.categoryHelp'),
    icon: 'Collection',
    action: () => {
      ElMessage.success(t('uxDemo.msgViewExamplesTriggered'))
    }
  },
  {
    id: 'open-settings',
    name: t('uxDemo.cmdOpenSettingsName'),
    description: t('uxDemo.cmdOpenSettingsDesc'),
    category: t('uxDemo.categorySystem'),
    icon: 'Setting',
    action: () => {
      ElMessage.success(t('uxDemo.msgOpenSettingsTriggered'))
    }
  }
])

// 组件引用
const tourRef = ref<InstanceType<typeof Tour> | null>(null)
const commandPaletteRef = ref<{ open: () => void } | null>(null)

// 统计数据
const exampleCount = computed(() => exampleProjects.length)
const commandCount = computed(() => registeredCommands.value.length)

// 方法
function startTour() {
  tourRef.value?.start()
}

function openCommandPalette() {
  commandPaletteRef.value?.open()
}

function onTourStart() {
  // 引导流程开始
}

function onTourStepChange(_index: number) {
  // 引导步骤变化回调（由 Tour 子组件触发，无需额外处理）
}

function onTourFinish() {
  ElMessage.success(t('uxDemo.msgTourCompleted'))
}

function onTourSkip(index: number) {
  ElMessage.info(t('uxDemo.msgTourSkipped', { step: index + 1 }))
}

function onCommandExecute(_command: Command) {
  // 命令执行回调（由命令面板触发，无需额外处理）
}

// 生命周期
onMounted(() => {
  // UX 演示页面已加载
})
</script>

<style scoped lang="scss">
.ux-demo {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;

  .demo-section {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h3 {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
      }

      .header-actions {
        display: flex;
        gap: 12px;
      }
    }

    .feature-list {
      margin-top: 20px;

      h4 {
        margin: 0 0 16px;
        font-size: 16px;
        font-weight: 600;
        color: var(--text-primary);
      }

      .feature-desc {
        margin-left: 12px;
        color: var(--text-secondary);
        font-size: 14px;
      }
    }
  }
}
</style>
