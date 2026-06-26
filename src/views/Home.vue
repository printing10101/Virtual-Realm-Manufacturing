<template>
  <div class="home-page">
    <!-- 顶部欢迎横幅 -->
    <section class="hero-banner">
      <div class="hero-content">
        <div class="hero-text">
          <h1>{{ $t('home.welcome') }}</h1>
          <p>{{ $t('home.welcomeDesc') }}</p>
        </div>
        <div class="hero-actions">
          <el-button type="primary" size="large" @click="$router.push('/workspace')">
            <el-icon><EditPen /></el-icon>
            {{ $t('app.newProject') }}
          </el-button>
          <el-button size="large" @click="emit('open-project')">
            <el-icon><FolderOpened /></el-icon>
            {{ $t('app.openProject') }}
          </el-button>
        </div>
      </div>
      <div class="hero-decoration">
        <svg viewBox="0 0 200 200" class="hero-svg">
          <g transform="translate(100,100)">
            <polygon :points="cubeFront" class="cube-face front" />
            <polygon :points="cubeBack" class="cube-face back" />
            <line v-for="(l, i) in cubeEdges" :key="i"
              :x1="l[0]" :y1="l[1]" :x2="l[2]" :y2="l[3]" class="cube-edge" />
            <circle v-for="(v, i) in cubeVertices" :key="'v'+i"
              :cx="v[0]" :cy="v[1]" r="2.5" class="cube-dot" />
          </g>
        </svg>
      </div>
    </section>

    <!-- 快捷功能入口 -->
    <section class="quick-access">
      <h3 class="section-title">{{ $t('home.quickAccess') || '快捷功能' }}</h3>
      <div class="feature-grid">
        <div v-for="item in featureItems" :key="item.path"
          class="feature-card" @click="$router.push(item.path)">
          <div class="feature-icon" :style="{ background: item.color }">
            <el-icon :size="24"><component :is="item.icon" /></el-icon>
          </div>
          <div class="feature-info">
            <span class="feature-name">{{ item.label }}</span>
            <span class="feature-desc">{{ item.desc }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 下方两栏：最近项目 + 系统状态 -->
    <section class="bottom-row">
      <div class="recent-projects">
        <h3 class="section-title">{{ $t('home.recentProjects') || '最近项目' }}</h3>
        <div v-if="loading" class="loading-placeholder">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ $t('common.loading') }}</span>
        </div>
        <div v-else-if="loadFailed || !recentProjects.length" class="empty-placeholder">
          <el-icon :size="40" color="var(--text-tertiary)"><FolderOpened /></el-icon>
          <p>{{ loadFailed ? ($t('home.fetchFailed') || '获取失败') : ($t('home.noRecentProject') || '暂无最近项目') }}</p>
          <el-button type="primary" text @click="emit('open-project')">
            {{ $t('app.openProject') }}
          </el-button>
        </div>
        <div v-else class="project-list">
          <div v-for="proj in recentProjects" :key="proj.path"
            class="project-item" @click="handleOpenProject(proj)">
            <div class="project-icon">
              <el-icon :size="20"><Document /></el-icon>
            </div>
            <div class="project-meta">
              <span class="project-name">{{ proj.name }}</span>
              <span class="project-time">{{ formatDate(proj.modified_at) }}</span>
            </div>
            <span class="project-size">{{ formatSize(proj.file_size) }}</span>
          </div>
        </div>
      </div>

      <div class="system-status">
        <h3 class="section-title">{{ $t('home.systemStatus') }}</h3>
        <div class="status-list">
          <div class="status-row">
            <span class="status-label">{{ $t('home.aiService') }}</span>
            <el-tag v-if="loading" type="info" class="status-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span class="status-loading-text">{{ $t('common.loading') }}</span>
            </el-tag>
            <el-tag v-else-if="loadFailed" type="danger">{{ $t('home.fetchFailed') }}</el-tag>
            <el-tag v-else-if="aiServiceStatus === 'running'" type="success">{{ $t('home.running') }}</el-tag>
            <el-tag v-else type="warning">{{ $t('home.stopped') }}</el-tag>
          </div>
          <div class="status-row">
            <span class="status-label">{{ $t('home.registeredModels') }}</span>
            <span v-if="loading" class="stat-value status-loading">
              <el-icon class="is-loading"><Loading /></el-icon>
            </span>
            <span v-else-if="loadFailed" class="stat-value stat-failed">{{ $t('home.fetchFailed') }}</span>
            <span v-else class="stat-value">{{ modelCount }}</span>
          </div>
          <div class="status-row">
            <span class="status-label">{{ $t('home.frontendVersion') || '前端版本' }}</span>
            <span class="stat-value">v{{ frontendVersion }}</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, markRaw, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Loading, EditPen, FolderOpened, Document, SetUp,
  Monitor, Cpu, Files, Grid, DataLine, ShoppingBag,
} from '@element-plus/icons-vue'
import http from '@/utils/http'
import { useVersionStore } from '@/stores/version'
import { useProjectStore } from '@/stores/project'
import type { ProjectSummary } from '@/types'

const { t } = useI18n()

const emit = defineEmits<{ (e: 'open-project'): void }>()
const router = useRouter()
const versionStore = useVersionStore()
const projectStore = useProjectStore()

const frontendVersion = computed(() => versionStore.frontendVersion)

const aiServiceStatus = ref<'running' | 'stopped' | 'unknown'>('unknown')
const modelCount = ref(0)
const loading = ref(true)
const loadFailed = ref(false)
const recentProjects = ref<ProjectSummary[]>([])

const REQUEST_TIMEOUT = 10000

interface FeatureItem {
  label: string
  desc: string
  icon: Component
  color: string
  path: string
}

const featureItems: FeatureItem[] = [
  { label: t('home.featureItems.workspace.label'), desc: t('home.featureItems.workspace.desc'), icon: markRaw(Grid), color: 'linear-gradient(135deg,#4A90D9,#357ABD)', path: '/workspace' },
  { label: t('home.featureItems.ruleEditor.label'), desc: t('home.featureItems.ruleEditor.desc'), icon: markRaw(SetUp), color: 'linear-gradient(135deg,#67A67A,#4E8C5F)', path: '/rule-editor' },
  { label: t('home.featureItems.toolpathEditor.label'), desc: t('home.featureItems.toolpathEditor.desc'), icon: markRaw(EditPen), color: 'linear-gradient(135deg,#D4A857,#B8903E)', path: '/toolpath-editor' },
  { label: t('home.featureItems.processPlanning.label'), desc: t('home.featureItems.processPlanning.desc'), icon: markRaw(DataLine), color: 'linear-gradient(135deg,#7B9AAF,#5F8299)', path: '/process-planning' },
  { label: t('home.featureItems.templateMarket.label'), desc: t('home.featureItems.templateMarket.desc'), icon: markRaw(ShoppingBag), color: 'linear-gradient(135deg,#C76B6B,#A85555)', path: '/template-market' },
  { label: t('home.featureItems.taskBoard.label'), desc: t('home.featureItems.taskBoard.desc'), icon: markRaw(Files), color: 'linear-gradient(135deg,#8B7D6B,#6B5D4F)', path: '/task-board' },
]

// 3D cube decoration
const cubeSize = 50
const angle = Math.PI / 6
const cos = Math.cos(angle)
const sin = Math.sin(angle)
const s = cubeSize
const cubeFront = `0,${-s} ${s * cos},${-s + s * sin} 0,0 ${-s * cos},${-s + s * sin}`
const cubeBack = `${25},${-s - 15} ${25 + s * cos},${-s + s * sin - 15} ${25},${-15} ${25 - s * cos},${-s + s * sin - 15}`
const cubeEdges = [
  [0, -s, 25, -s - 15],
  [s * cos, -s + s * sin, 25 + s * cos, -s + s * sin - 15],
  [0, 0, 25, -15],
  [-s * cos, -s + s * sin, 25 - s * cos, -s + s * sin - 15],
]
const cubeVertices = [
  [0, -s], [s * cos, -s + s * sin], [0, 0], [-s * cos, -s + s * sin],
  [25, -s - 15], [25 + s * cos, -s + s * sin - 15], [25, -15], [25 - s * cos, -s + s * sin - 15],
]

async function loadHealth(): Promise<boolean> {
  try {
    const res = await http.get('/api/health', { timeout: REQUEST_TIMEOUT })
    const data = res.data?.data ?? res.data ?? {}
    const rawStatus = (data.status ?? data.ai_service ?? data.aiService ?? '').toString().toLowerCase()
    if (['running', 'ok', 'healthy', 'up'].includes(rawStatus)) {
      aiServiceStatus.value = 'running'
    } else if (['stopped', 'down', 'unhealthy'].includes(rawStatus)) {
      aiServiceStatus.value = 'stopped'
    } else {
      aiServiceStatus.value = 'running'
    }
    return true
  } catch {
    return false
  }
}

async function loadModelCount(): Promise<boolean> {
  try {
    const res = await http.get('/api/v1/lnn/models', { timeout: REQUEST_TIMEOUT })
    const data = res.data?.data ?? res.data ?? {}
    const total = data.total ?? data.count ?? data.model_count
    if (typeof total === 'number') modelCount.value = total
    else if (Array.isArray(data.models)) modelCount.value = data.models.length
    else modelCount.value = 0
    return true
  } catch {
    return false
  }
}

async function loadRecentProjects() {
  try {
    await projectStore.fetchProjectList()
    const list = projectStore.projectList || []
    recentProjects.value = list.slice(0, 5)
  } catch {
    recentProjects.value = []
  }
}

function handleOpenProject(proj: ProjectSummary) {
  projectStore.openProject(proj.path)
  router.push('/workspace')
}

function formatDate(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  const locale = localStorage.getItem('app_locale') || 'zh-CN'
  return d.toLocaleString(locale === 'en' ? 'en-US' : 'zh-CN', { hour12: false })
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0; let s = bytes
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++ }
  return s.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

onMounted(async () => {
  loading.value = true
  loadFailed.value = false
  try {
    const results = await Promise.all([loadHealth(), loadModelCount()])
    if (results.some(ok => !ok)) loadFailed.value = true
  } catch {
    loadFailed.value = true
  } finally {
    loading.value = false
  }
  loadRecentProjects()
})
</script>

<style scoped>
.home-page {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
}

/* ===== Hero Banner ===== */
.hero-banner {
  position: relative;
  background: linear-gradient(135deg, #2C3E6B 0%, #1A2744 60%, #0F1B33 100%);
  border-radius: 16px;
  padding: 40px 44px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hero-content {
  position: relative;
  z-index: 1;
  flex: 1;
}

.hero-text h1 {
  margin: 0 0 10px;
  font-size: 1.75rem;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.04em;
}

.hero-text p {
  margin: 0 0 28px;
  font-size: 0.95rem;
  color: rgba(255, 255, 255, 0.65);
  line-height: 1.6;
  max-width: 420px;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.hero-actions .el-button--primary {
  --el-button-bg-color: #4A90D9;
  --el-button-border-color: #4A90D9;
  --el-button-hover-bg-color: #5BA0E9;
  --el-button-hover-border-color: #5BA0E9;
}

.hero-actions .el-button:not(.el-button--primary) {
  --el-button-bg-color: rgba(255,255,255,0.12);
  --el-button-border-color: rgba(255,255,255,0.25);
  --el-button-text-color: #fff;
  --el-button-hover-bg-color: rgba(255,255,255,0.2);
  --el-button-hover-border-color: rgba(255,255,255,0.4);
  --el-button-hover-text-color: #fff;
}

.hero-decoration {
  position: absolute;
  right: 30px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.15;
  pointer-events: none;
}

.hero-svg {
  width: 220px;
  height: 220px;
  animation: hero-rotate 20s linear infinite;
}

@keyframes hero-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.cube-face.front {
  fill: rgba(74, 144, 217, 0.15);
  stroke: rgba(74, 144, 217, 0.8);
  stroke-width: 1.5;
}
.cube-face.back {
  fill: none;
  stroke: rgba(74, 144, 217, 0.4);
  stroke-width: 1;
}
.cube-edge {
  stroke: rgba(74, 144, 217, 0.6);
  stroke-width: 1;
}
.cube-dot {
  fill: rgba(255, 255, 255, 0.9);
}

/* ===== Section Title ===== */
.section-title {
  margin: 0 0 16px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

/* ===== Quick Access Grid ===== */
.feature-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.feature-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  cursor: pointer;
  transition: all var(--transition-normal);
}

.feature-card:hover {
  border-color: var(--accent-light);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.feature-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}

.feature-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.feature-name {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-primary);
}

.feature-desc {
  font-size: 0.8rem;
  color: var(--text-tertiary);
}

/* ===== Bottom Row ===== */
.bottom-row {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 20px;
}

.recent-projects,
.system-status {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 12px;
  padding: 24px;
}

.loading-placeholder,
.empty-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 0;
  color: var(--text-tertiary);
  font-size: 0.9rem;
}

.project-list {
  display: flex;
  flex-direction: column;
}

.project-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.project-item:hover {
  background: var(--bg-secondary);
}

.project-item + .project-item {
  border-top: 1px solid var(--border-light);
}

.project-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent-primary);
  flex-shrink: 0;
}

.project-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.project-name {
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-time {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

.project-size {
  font-size: 0.8rem;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* ===== System Status ===== */
.status-list {
  display: flex;
  flex-direction: column;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 0;
  border-bottom: 1px solid var(--border-light);
}

.status-row:last-child {
  border-bottom: none;
}

.status-label {
  font-size: 0.9rem;
  color: var(--text-secondary);
}

.stat-value {
  font-weight: 600;
  color: var(--accent-primary);
  font-size: 0.95rem;
}

.stat-failed {
  color: var(--error);
  font-weight: normal;
  font-size: 0.85rem;
}

.status-loading {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.status-loading-text {
  margin-left: 2px;
  color: var(--text-tertiary);
}
</style>
