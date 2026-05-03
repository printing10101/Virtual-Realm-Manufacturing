<template>
  <div class="workspace-view">
    <el-card class="workspace-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('workspace.title') }}</h2>
          <div class="header-actions">
            <el-input
              v-model="searchQuery"
              :placeholder="t('workspace.search')"
              prefix-icon="Search"
              style="width: 240px; margin-right: 12px"
              clearable
            />
            <el-button type="primary" @click="handleCreateProject">
              <el-icon><Plus /></el-icon>
              {{ t('workspace.newProject') }}
            </el-button>
          </div>
        </div>
      </template>
      
      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('workspace.allProjects')" name="all">
          <div v-if="projects.length === 0" class="empty-state">
            <el-empty :description="t('workspace.noProjects')" :image-size="180">
              <el-button type="primary" @click="handleCreateProject">
                {{ t('workspace.createFirst') }}
              </el-button>
            </el-empty>
          </div>
          <el-row v-else :gutter="20">
            <el-col :xs="24" :sm="12" :md="8" :lg="6" v-for="project in filteredProjects" :key="project.id">
              <el-card shadow="hover" class="project-card card-hover">
                <div class="project-cover">
                  <el-icon size="64" color="#c0c4cc"><Files /></el-icon>
                </div>
                <div class="project-info">
                  <h4>{{ project.name }}</h4>
                  <p class="project-desc">{{ project.description || t('workspace.noDescription') }}</p>
                  <div class="project-meta">
                    <el-tag size="small" :type="getStatusType(project.status)">{{ project.status }}</el-tag>
                    <span class="update-time">{{ formatTime(project.updated_at) }}</span>
                  </div>
                </div>
                <div class="project-actions">
                  <el-button text type="primary" size="small" @click="handleOpenProject(project)">
                    {{ t('workspace.open') }}
                  </el-button>
                  <el-button text type="danger" size="small" @click="handleDeleteProject(project)">
                    {{ t('workspace.delete') }}
                  </el-button>
                </div>
              </el-card>
            </el-col>
          </el-row>
        </el-tab-pane>
        
        <el-tab-pane :label="t('workspace.recent')" name="recent">
          <el-empty :description="t('workspace.noRecent')" />
        </el-tab-pane>
        
        <el-tab-pane :label="t('workspace.favorites')" name="favorites">
          <el-empty :description="t('workspace.noFavorites')" />
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog v-model="showCreateDialog" :title="t('workspace.createProject')" width="500px">
      <el-form :model="newProject" label-width="80px">
        <el-form-item :label="t('workspace.projectName')">
          <el-input v-model="newProject.name" :placeholder="t('workspace.projectNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('workspace.description')">
          <el-input v-model="newProject.description" type="textarea" :rows="3" :placeholder="t('workspace.descriptionPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">{{ t('workspace.cancel') }}</el-button>
        <el-button type="primary" @click="confirmCreateProject">{{ t('workspace.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Plus, Files } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useProjectStore } from '@/stores/projectStore'
import { handleError } from '@/utils/errorHandler'
import type { ProjectMeta } from '@/types/persistence'

const { t } = useI18n()
const projectStore = useProjectStore()

const activeTab = ref('all')
const searchQuery = ref('')
const showCreateDialog = ref(false)

const projects = computed(() => projectStore.projects)

const newProject = ref({
  name: '',
  description: ''
})

const filteredProjects = computed(() => {
  if (!searchQuery.value) return projects.value
  return projects.value.filter(p => 
    p.name.toLowerCase().includes(searchQuery.value.toLowerCase())
  )
})

function getStatusType(status: string) {
  const map: Record<string, string> = {
    'draft': 'info',
    'processing': '',
    'completed': 'success'
  }
  return map[status] || 'info'
}

function formatTime(timeStr?: string) {
  if (!timeStr) return ''
  try {
    const date = new Date(timeStr)
    return date.toLocaleDateString()
  } catch {
    return timeStr
  }
}

function handleCreateProject() {
  newProject.value = { name: '', description: '' }
  showCreateDialog.value = true
}

async function confirmCreateProject() {
  if (!newProject.value.name.trim()) {
    ElMessage.warning(t('workspace.nameRequired'))
    return
  }
  
  try {
    await projectStore.createProject(newProject.value.name, newProject.value.description)
    showCreateDialog.value = false
    ElMessage.success(t('workspace.createSuccess'))
  } catch (error) {
    handleError(error)
  }
}

function handleOpenProject(project: ProjectMeta) {
  projectStore.selectProject(project)
  ElMessage.info(`${t('workspace.open')}: ${project.name}`)
}

async function handleDeleteProject(project: ProjectMeta) {
  ElMessageBox.confirm(
    `${t('workspace.confirmDelete')} ${project.name}?`,
    t('workspace.warning'),
    { type: 'warning' }
  ).then(async () => {
    try {
      await projectStore.deleteProject(project.id)
      ElMessage.success(t('workspace.deleteSuccess'))
    } catch (error) {
      handleError(error)
    }
  }).catch(() => {})
}

onMounted(async () => {
  await projectStore.loadProjects()
})
</script>

<style scoped lang="scss">
.workspace-view {
  .workspace-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      h2 {
        margin: 0;
        font-size: 20px;
        color: #303133;
      }
      
      .header-actions {
        display: flex;
        align-items: center;
      }
    }
  }
  
  .empty-state {
    padding: 60px 0;
    text-align: center;
  }
  
  .project-card {
    margin-bottom: 20px;
    
    .project-cover {
      height: 120px;
      display: flex;
      align-items: center;
      justify-content: center;
      background-color: #f5f7fa;
      border-radius: var(--lj-module-radius);
      margin-bottom: 12px;
    }
    
    .project-info {
      h4 {
        margin: 0 0 8px;
        font-size: 16px;
        color: #303133;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      
      .project-desc {
        margin: 0 0 12px;
        font-size: 13px;
        color: #909399;
        line-height: 1.4;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }
      
      .project-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .update-time {
          font-size: 12px;
          color: #c0c4cc;
        }
      }
    }
    
    .project-actions {
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid #ebeef5;
      display: flex;
      justify-content: space-between;
    }
  }
}

@media (max-width: 768px) {
  .workspace-view {
    .workspace-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
        
        .header-actions {
          width: 100%;
          
          .el-input {
            flex: 1;
          }
        }
      }
    }
  }
}
</style>
