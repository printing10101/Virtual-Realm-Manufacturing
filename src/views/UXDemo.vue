<template>
  <div class="ux-demo">
    <el-card class="demo-section">
      <template #header>
        <div class="card-header">
          <h3>UX 功能演示</h3>
          <div class="header-actions">
            <el-button type="primary" @click="startTour">
              <el-icon><Guide /></el-icon>
              启动引导流程
            </el-button>
            <el-button @click="openCommandPalette">
              <el-icon><Search /></el-icon>
              命令面板 (Ctrl+K)
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="20">
        <el-col :span="8">
          <el-statistic title="引导步骤数" :value="tourSteps.length" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="示例工程数" :value="exampleCount" />
        </el-col>
        <el-col :span="8">
          <el-statistic title="注册命令数" :value="commandCount" />
        </el-col>
      </el-row>

      <el-divider />

      <div class="feature-list">
        <h4>已实现功能</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="引导流程">
            <el-tag type="success">已完成</el-tag>
            <span class="feature-desc">5个步骤、进度记忆、响应式设计</span>
          </el-descriptions-item>
          <el-descriptions-item label="示例工程库">
            <el-tag type="success">已完成</el-tag>
            <span class="feature-desc">12个示例、搜索过滤、代码预览、一键复制</span>
          </el-descriptions-item>
          <el-descriptions-item label="命令面板">
            <el-tag type="success">已完成</el-tag>
            <span class="feature-desc">快捷键唤起、模糊搜索、智能排序、使用频率记忆</span>
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
        <h3>示例工程库预览</h3>
      </template>
      <ExampleGallery />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Guide, Search } from '@element-plus/icons-vue'
import Tour from '@/components/Onboarding/Tour.vue'
import type { TourStep } from '@/components/Onboarding/Tour.vue'
import CommandPalette from '@/components/CommandPalette/CommandPalette.vue'
import type { Command } from '@/composables/useCommandPalette'
import ExampleGallery from '@/examples/ExampleGallery.vue'
import { exampleProjects } from '@/examples/data'

// 引导步骤配置
const tourSteps: TourStep[] = [
  {
    title: '欢迎使用灵境制造系统',
    description: '这是一个AI驱动的3D建模与工艺规划系统。让我们通过几个简单的步骤来了解主要功能。',
    target: '.app-header',
    placement: 'bottom'
  },
  {
    title: '文件管理',
    description: '在这里可以新建、打开、保存工程项目，支持导入STEP和DXF格式文件。',
    target: '.header-right',
    placement: 'bottom'
  },
  {
    title: '导航菜单',
    description: '通过顶部菜单可以快速访问工作区、设置、工艺规划等核心功能模块。',
    target: '.header-menu',
    placement: 'bottom'
  },
  {
    title: '命令面板',
    description: '按 Ctrl+K 可以快速唤起命令面板，支持模糊搜索和智能排序，提升操作效率。',
    target: '.header-actions',
    placement: 'bottom'
  },
  {
    title: '准备开始',
    description: '引导已完成！您可以随时从帮助菜单重新启动引导流程。现在让我们开始探索系统的强大功能吧！',
    placement: 'center'
  }
]

// 注册命令
const registeredCommands = computed<Command[]>(() => [
  {
    id: 'new-project',
    name: '新建项目',
    description: '创建一个新的工程项目',
    category: '文件',
    icon: 'DocumentAdd',
    shortcut: 'Ctrl+N',
    action: () => {
      ElMessage.success('新建项目功能已触发')
    }
  },
  {
    id: 'open-project',
    name: '打开项目',
    description: '打开已有的工程项目',
    category: '文件',
    icon: 'FolderOpened',
    shortcut: 'Ctrl+O',
    action: () => {
      ElMessage.success('打开项目功能已触发')
    }
  },
  {
    id: 'save-project',
    name: '保存项目',
    description: '保存当前工程项目',
    category: '文件',
    icon: 'Download',
    shortcut: 'Ctrl+S',
    action: () => {
      ElMessage.success('保存项目功能已触发')
    }
  },
  {
    id: 'export-gcode',
    name: '导出G代码',
    description: '将工具路径导出为G代码文件',
    category: '工具路径',
    icon: 'Document',
    action: () => {
      ElMessage.success('导出G代码功能已触发')
    }
  },
  {
    id: 'start-simulation',
    name: '启动仿真',
    description: '开始加工过程仿真模拟',
    category: '仿真',
    icon: 'VideoPlay',
    action: () => {
      ElMessage.success('启动仿真功能已触发')
    }
  },
  {
    id: 'ai-feature-recognition',
    name: 'AI特征识别',
    description: '使用AI自动识别加工特征',
    category: 'AI',
    icon: 'MagicStick',
    action: () => {
      ElMessage.success('AI特征识别功能已触发')
    }
  },
  {
    id: 'view-examples',
    name: '查看示例',
    description: '浏览示例工程库',
    category: '帮助',
    icon: 'Collection',
    action: () => {
      ElMessage.success('查看示例功能已触发')
    }
  },
  {
    id: 'open-settings',
    name: '系统设置',
    description: '打开系统设置页面',
    category: '系统',
    icon: 'Setting',
    action: () => {
      ElMessage.success('系统设置功能已触发')
    }
  }
])

// 组件引用
const tourRef = ref<InstanceType<typeof Tour> | null>(null)
const commandPaletteRef = ref<any>(null)

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
  console.log('引导流程开始')
}

function onTourStepChange(index: number) {
  console.log('引导步骤变化:', index)
}

function onTourFinish() {
  ElMessage.success('引导流程已完成！')
}

function onTourSkip(index: number) {
  ElMessage.info(`引导流程已跳过（从第 ${index + 1} 步）`)
}

function onCommandExecute(command: Command) {
  console.log('命令已执行:', command.name)
}

// 生命周期
onMounted(() => {
  console.log('UX 演示页面已加载')
  console.log(`示例工程数量: ${exampleCount.value}`)
  console.log(`注册命令数量: ${commandCount.value}`)
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
        color: #303133;
      }

      .feature-desc {
        margin-left: 12px;
        color: #606266;
        font-size: 14px;
      }
    }
  }
}
</style>
