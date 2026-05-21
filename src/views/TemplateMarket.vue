<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

const trending = ref<any[]>([])
const templates = ref<any[]>([])
const subscriptions = ref<string[]>([])
const activeTab = ref('market')
const loading = ref(false)
const subscribeCategory = ref('')
const publishForm = ref({
  branch_id: '',
  name: '',
  category: 'general',
  description: ''
})

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

async function fetchTrending() {
  try {
    const res = await fetch(`${API_BASE}/template_market/trending`)
    const data = await res.json()
    if (data.code === 'SUCCESS') trending.value = data.data
  } catch { /* empty */ }
}

async function fetchTemplates() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/templates/branches`)
    const data = await res.json()
    if (data.code === 'SUCCESS') templates.value = data.data
  } catch { /* empty */ } finally {
    loading.value = false
  }
}

async function subscribe() {
  if (!subscribeCategory.value.trim()) return
  try {
    await fetch(`${API_BASE}/template_market/subscribe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: 'default', category: subscribeCategory.value })
    })
    subscriptions.value.push(subscribeCategory.value)
    subscribeCategory.value = ''
  } catch { /* empty */ }
}

async function publishTemplate() {
  if (!publishForm.value.branch_id || !publishForm.value.name) return
  try {
    await fetch(`${API_BASE}/template_market/publish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(publishForm.value)
    })
    publishForm.value = { branch_id: '', name: '', category: 'general', description: '' }
    fetchTrending()
  } catch { /* empty */ }
}

function viewDetail(branchId: string) {
  router.push(`/templates/${branchId}`)
}

function viewUpdates() {
  router.push('/template-updates')
}

function viewBranches() {
  router.push('/template-branches')
}

onMounted(() => {
  fetchTrending()
  fetchTemplates()
})
</script>

<template>
  <div class="template-market-page">
    <el-card class="header-card">
      <div class="page-header">
        <h2>模板市场</h2>
        <div class="header-actions">
          <el-button
            type="primary"
            @click="viewUpdates"
          >
            更新中心
          </el-button>
          <el-button @click="viewBranches">
            分支管理
          </el-button>
        </div>
      </div>
    </el-card>

    <el-tabs
      v-model="activeTab"
      class="main-tabs"
    >
      <el-tab-pane
        label="模板列表"
        name="market"
      >
        <div
          v-if="loading"
          class="loading"
        >
          加载中...
        </div>
        <el-row
          v-else
          :gutter="16"
        >
          <el-col
            v-for="tpl in templates"
            :key="tpl.branch_id"
            :span="8"
          >
            <el-card
              shadow="hover"
              class="template-card"
              @click="viewDetail(tpl.branch_id)"
            >
              <template #header>
                <div class="card-header">
                  <span class="template-name">{{ tpl.name }}</span>
                  <el-tag
                    size="small"
                    :type="tpl.metadata?.type === 'main' ? 'success' : 'info'"
                  >
                    {{ tpl.metadata?.type || 'unknown' }}
                  </el-tag>
                </div>
              </template>
              <div class="template-meta">
                <div>更新时间: {{ new Date(tpl.updated_at * 1000).toLocaleDateString() }}</div>
                <div>提交记录: {{ tpl.commit_log?.length || 0 }} 条</div>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-tab-pane>

      <el-tab-pane
        label="热度榜"
        name="trending"
      >
        <el-table
          :data="trending"
          stripe
        >
          <el-table-column
            prop="name"
            label="模板名称"
          />
          <el-table-column
            prop="category"
            label="分类"
            width="120"
          />
          <el-table-column
            prop="adoption_count"
            label="采用次数"
            width="120"
            sortable
          />
          <el-table-column
            label="操作"
            width="100"
          >
            <template #default="{ row }">
              <el-button
                size="small"
                @click="viewDetail(row.branch_id)"
              >
                查看
              </el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty
          v-if="trending.length === 0"
          description="暂无热度数据"
        />
      </el-tab-pane>

      <el-tab-pane
        label="订阅"
        name="subscribe"
      >
        <div class="subscribe-section">
          <el-input
            v-model="subscribeCategory"
            placeholder="输入行业或材料类别"
            style="width: 300px; margin-right: 12px;"
          >
            <template #append>
              <el-button @click="subscribe">
                订阅
              </el-button>
            </template>
          </el-input>
          <el-tag
            v-for="cat in subscriptions"
            :key="cat"
            closable
            style="margin: 4px;"
            @close="subscriptions = subscriptions.filter(c => c !== cat)"
          >
            {{ cat }}
          </el-tag>
          <el-empty
            v-if="subscriptions.length === 0"
            description="暂无订阅"
          />
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="发布"
        name="publish"
      >
        <el-form
          :model="publishForm"
          label-width="100px"
          style="max-width: 500px;"
        >
          <el-form-item label="分支ID">
            <el-input
              v-model="publishForm.branch_id"
              placeholder="选择要发布的分支ID"
            />
          </el-form-item>
          <el-form-item label="模板名称">
            <el-input
              v-model="publishForm.name"
              placeholder="模板显示名称"
            />
          </el-form-item>
          <el-form-item label="分类">
            <el-select v-model="publishForm.category">
              <el-option
                label="通用"
                value="general"
              />
              <el-option
                label="汽车行业"
                value="automotive"
              />
              <el-option
                label="航空航天"
                value="aerospace"
              />
              <el-option
                label="模具"
                value="mold"
              />
              <el-option
                label="45钢"
                value="steel_45"
              />
              <el-option
                label="铝合金"
                value="aluminum"
              />
              <el-option
                label="钛合金"
                value="titanium"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="publishForm.description"
              type="textarea"
              :rows="3"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              @click="publishTemplate"
            >
              发布到市场
            </el-button>
          </el-form-item>
        </el-form>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.template-market-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { margin: 0; }
.main-tabs { margin-top: 16px; }
.template-card { cursor: pointer; margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.template-name { font-weight: 600; font-size: 16px; }
.template-meta { color: #666; font-size: 13px; line-height: 1.8; }
.loading { text-align: center; padding: 40px; color: #999; }
.subscribe-section { padding: 20px 0; }
.header-card { margin-bottom: 16px; }
</style>
