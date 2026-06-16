<template>
  <div class="example-gallery">
    <!-- 搜索和过滤区域 -->
    <el-card class="filter-card" shadow="never">
      <el-row :gutter="16">
        <el-col :span="8">
          <el-input
            v-model="filter.keyword"
            placeholder="搜索示例..."
            clearable
            prefix-icon="Search"
          />
        </el-col>
        <el-col :span="4">
          <el-select v-model="filter.category" placeholder="分类" clearable>
            <el-option
              v-for="cat in categories"
              :key="cat.value"
              :label="cat.label"
              :value="cat.value"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filter.difficulty" placeholder="难度" clearable>
            <el-option
              v-for="diff in difficulties"
              :key="diff.value"
              :label="diff.label"
              :value="diff.value"
            />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filter.sortBy" placeholder="排序">
            <el-option label="名称" value="name" />
            <el-option label="更新时间" value="date" />
            <el-option label="下载次数" value="downloads" />
            <el-option label="难度" value="difficulty" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-button-group>
            <el-button
              :type="viewMode === 'grid' ? 'primary' : 'default'"
              icon="Grid"
              @click="viewMode = 'grid'"
            />
            <el-button
              :type="viewMode === 'list' ? 'primary' : 'default'"
              icon="List"
              @click="viewMode = 'list'"
            />
          </el-button-group>
        </el-col>
      </el-row>
    </el-card>

    <!-- 示例列表 -->
    <div v-if="viewMode === 'grid'" class="example-grid">
      <el-card
        v-for="example in filteredExamples"
        :key="example.id"
        class="example-card"
        shadow="hover"
        @click="handleSelect(example)"
      >
        <template #header>
          <div class="card-header">
            <div class="card-title">
              <h4>{{ example.name }}</h4>
              <el-tag :type="getDifficultyType(example.difficulty)" size="small">
                {{ getDifficultyLabel(example.difficulty) }}
              </el-tag>
            </div>
            <div class="card-category">
              <el-tag type="info" size="small" effect="plain">
                {{ getCategoryLabel(example.category) }}
              </el-tag>
            </div>
          </div>
        </template>

        <p class="card-description">{{ example.description }}</p>

        <div class="card-tags">
          <el-tag
            v-for="tag in example.tags.slice(0, 3)"
            :key="tag"
            size="small"
            effect="plain"
            class="tag-item"
          >
            {{ tag }}
          </el-tag>
        </div>

        <div class="card-footer">
          <div class="card-stats">
            <span class="stat-item">
              <el-icon><Download /></el-icon>
              {{ example.downloadCount }}
            </span>
            <span class="stat-item">
              <el-icon><Clock /></el-icon>
              {{ formatDate(example.updatedAt) }}
            </span>
          </div>
          <div class="card-actions">
            <el-button
              size="small"
              icon="View"
              @click.stop="handlePreview(example)"
            >
              预览
            </el-button>
            <el-button
              size="small"
              type="primary"
              icon="CopyDocument"
              @click.stop="handleCopy(example)"
            >
              复制
            </el-button>
          </div>
        </div>
      </el-card>
    </div>

    <div v-else class="example-list">
      <el-table
        :data="filteredExamples"
        stripe
        @row-click="handleSelect"
      >
        <el-table-column prop="name" label="名称" width="200">
          <template #default="{ row }">
            <div class="table-name">
              <strong>{{ row.name }}</strong>
              <el-tag :type="getDifficultyType(row.difficulty)" size="small">
                {{ getDifficultyLabel(row.difficulty) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="300" />
        <el-table-column prop="category" label="分类" width="120">
          <template #default="{ row }">
            <el-tag type="info" size="small" effect="plain">
              {{ getCategoryLabel(row.category) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="downloadCount" label="下载" width="100" sortable />
        <el-table-column prop="updatedAt" label="更新时间" width="120">
          <template #default="{ row }">
            {{ formatDate(row.updatedAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              icon="View"
              @click.stop="handlePreview(row)"
            >
              预览
            </el-button>
            <el-button
              size="small"
              type="primary"
              icon="CopyDocument"
              @click.stop="handleCopy(row)"
            >
              复制
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 详情对话框 -->
    <el-dialog
      v-model="showDetail"
      :title="selectedExample?.name"
      width="800px"
      top="5vh"
    >
      <div v-if="selectedExample" class="example-detail">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="说明" name="details">
            <div class="detail-section">
              <div class="detail-meta">
                <el-tag :type="getDifficultyType(selectedExample.difficulty)">
                  {{ getDifficultyLabel(selectedExample.difficulty) }}
                </el-tag>
                <el-tag type="info" effect="plain">
                  {{ getCategoryLabel(selectedExample.category) }}
                </el-tag>
                <span class="meta-item">
                  <el-icon><Download /></el-icon>
                  {{ selectedExample.downloadCount }} 次下载
                </span>
                <span class="meta-item">
                  <el-icon><Clock /></el-icon>
                  更新于 {{ formatDate(selectedExample.updatedAt) }}
                </span>
              </div>

              <div class="detail-content" v-html="renderMarkdown(selectedExample.details)" />

              <div class="detail-use-cases">
                <h4>应用场景</h4>
                <ul>
                  <li v-for="useCase in selectedExample.useCases" :key="useCase">
                    {{ useCase }}
                  </li>
                </ul>
              </div>
            </div>
          </el-tab-pane>

          <el-tab-pane label="代码" name="code">
            <div class="code-section">
              <div class="code-header">
                <span class="code-language">{{ selectedExample.language }}</span>
                <el-button
                  type="primary"
                  size="small"
                  icon="CopyDocument"
                  @click="handleCopyCode"
                >
                  复制代码
                </el-button>
              </div>
              <pre class="code-block"><code>{{ selectedExample.code }}</code></pre>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>

      <template #footer>
        <el-button @click="showDetail = false">关闭</el-button>
        <el-button
          type="primary"
          icon="Download"
          @click="handleImport(selectedExample!)"
        >
          导入到项目
        </el-button>
      </template>
    </el-dialog>

    <!-- 预览对话框 -->
    <el-dialog
      v-model="showPreview"
      title="代码预览"
      width="700px"
    >
      <div v-if="previewExample" class="preview-content">
        <pre class="code-block"><code>{{ previewExample.code }}</code></pre>
      </div>
      <template #footer>
        <el-button @click="showPreview = false">关闭</el-button>
        <el-button
          type="primary"
          icon="CopyDocument"
          @click="handleCopy(previewExample!)"
        >
          复制代码
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Clock, Search, Grid, List, View, CopyDocument } from '@element-plus/icons-vue'
import type { ExampleProject, ExampleFilter, ExampleCategory, ExampleDifficulty } from './types'
import { exampleProjects, getCategories, getDifficulties } from './data'

// 状态
const filter = ref<ExampleFilter>({
  keyword: '',
  category: 'all',
  difficulty: 'all',
  sortBy: 'downloads',
  sortOrder: 'desc'
})

const viewMode = ref<'grid' | 'list'>('grid')
const showDetail = ref(false)
const showPreview = ref(false)
const selectedExample = ref<ExampleProject | null>(null)
const previewExample = ref<ExampleProject | null>(null)
const activeTab = ref('details')

// 计算属性
const categories = getCategories()
const difficulties = getDifficulties()

const filteredExamples = computed(() => {
  let result = [...exampleProjects]

  // 关键词搜索
  if (filter.value.keyword) {
    const keyword = filter.value.keyword.toLowerCase()
    result = result.filter(example =>
      example.name.toLowerCase().includes(keyword) ||
      example.description.toLowerCase().includes(keyword) ||
      example.tags.some(tag => tag.toLowerCase().includes(keyword))
    )
  }

  // 分类过滤
  if (filter.value.category && filter.value.category !== 'all') {
    result = result.filter(example => example.category === filter.value.category)
  }

  // 难度过滤
  if (filter.value.difficulty && filter.value.difficulty !== 'all') {
    result = result.filter(example => example.difficulty === filter.value.difficulty)
  }

  // 排序
  if (filter.value.sortBy) {
    result.sort((a, b) => {
      let compareValue = 0
      
      switch (filter.value.sortBy) {
        case 'name':
          compareValue = a.name.localeCompare(b.name)
          break
        case 'date':
          compareValue = new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          break
        case 'downloads':
          compareValue = b.downloadCount - a.downloadCount
          break
        case 'difficulty':
          const difficultyOrder = { beginner: 1, intermediate: 2, advanced: 3 }
          compareValue = difficultyOrder[a.difficulty] - difficultyOrder[b.difficulty]
          break
      }

      return filter.value.sortOrder === 'asc' ? compareValue : -compareValue
    })
  }

  return result
})

// 方法
function handleSelect(example: ExampleProject) {
  selectedExample.value = example
  showDetail.value = true
  activeTab.value = 'details'
}

function handlePreview(example: ExampleProject) {
  previewExample.value = example
  showPreview.value = true
}

async function handleCopy(example: ExampleProject) {
  try {
    await navigator.clipboard.writeText(example.code)
    ElMessage.success('代码已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败，请手动复制')
  }
}

function handleCopyCode() {
  if (selectedExample.value) {
    handleCopy(selectedExample.value)
  }
}

function handleImport(example: ExampleProject) {
  // 这里可以实现导入逻辑
  ElMessage.success(`示例 "${example.name}" 已导入到项目`)
  showDetail.value = false
}

function getDifficultyType(difficulty: ExampleDifficulty) {
  const typeMap = {
    beginner: 'success',
    intermediate: 'warning',
    advanced: 'danger'
  }
  return typeMap[difficulty]
}

function getDifficultyLabel(difficulty: ExampleDifficulty) {
  const labelMap = {
    beginner: '入门',
    intermediate: '中级',
    advanced: '高级'
  }
  return labelMap[difficulty]
}

function getCategoryLabel(category: ExampleCategory) {
  const categoryMap = {
    basic: '基础示例',
    modeling: '3D建模',
    toolpath: '工具路径',
    simulation: '仿真模拟',
    ai: 'AI功能',
    advanced: '高级应用'
  }
  return categoryMap[category]
}

function formatDate(dateString: string) {
  const date = new Date(dateString)
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })
}

function renderMarkdown(content: string) {
  // 简单的 Markdown 渲染（实际项目中可以使用 markdown-it 等库）
  return content
    .replace(/^### (.*$)/gim, '<h3>$1</h3>')
    .replace(/^## (.*$)/gim, '<h2>$1</h2>')
    .replace(/^# (.*$)/gim, '<h1>$1</h1>')
    .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
    .replace(/\*(.*)\*/gim, '<em>$1</em>')
    .replace(/`(.*?)`/gim, '<code>$1</code>')
    .replace(/\n/gim, '<br>')
}
</script>

<style scoped lang="scss">
.example-gallery {
  padding: 20px;

  .filter-card {
    margin-bottom: 20px;

    :deep(.el-card__body) {
      padding: 16px;
    }
  }

  .example-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;

    .example-card {
      cursor: pointer;
      transition: all 0.3s;

      &:hover {
        transform: translateY(-4px);
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 12px;

        .card-title {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 8px;

          h4 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
          }
        }
      }

      .card-description {
        margin: 12px 0;
        color: #606266;
        font-size: 14px;
        line-height: 1.5;
      }

      .card-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-bottom: 12px;

        .tag-item {
          font-size: 12px;
        }
      }

      .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding-top: 12px;
        border-top: 1px solid #ebeef5;

        .card-stats {
          display: flex;
          gap: 16px;
          color: #909399;
          font-size: 13px;

          .stat-item {
            display: flex;
            align-items: center;
            gap: 4px;
          }
        }

        .card-actions {
          display: flex;
          gap: 8px;
        }
      }
    }
  }

  .example-list {
    .table-name {
      display: flex;
      flex-direction: column;
      gap: 6px;

      strong {
        font-size: 14px;
      }
    }
  }

  .example-detail {
    .detail-section {
      .detail-meta {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 20px;
        padding-bottom: 16px;
        border-bottom: 1px solid #ebeef5;

        .meta-item {
          display: flex;
          align-items: center;
          gap: 4px;
          color: #909399;
          font-size: 13px;
        }
      }

      .detail-content {
        line-height: 1.8;
        color: #606266;

        :deep(h1), :deep(h2), :deep(h3) {
          margin: 20px 0 12px;
          color: #303133;
        }

        :deep(h1) {
          font-size: 20px;
        }

        :deep(h2) {
          font-size: 18px;
        }

        :deep(h3) {
          font-size: 16px;
        }

        :deep(ul) {
          padding-left: 20px;
          margin: 12px 0;
        }

        :deep(li) {
          margin: 6px 0;
        }

        :deep(code) {
          background-color: #f5f7fa;
          padding: 2px 6px;
          border-radius: 3px;
          font-family: 'Courier New', monospace;
          font-size: 13px;
        }
      }

      .detail-use-cases {
        margin-top: 24px;
        padding: 16px;
        background-color: #f5f7fa;
        border-radius: 6px;

        h4 {
          margin: 0 0 12px;
          font-size: 15px;
          color: #303133;
        }

        ul {
          margin: 0;
          padding-left: 20px;

          li {
            margin: 8px 0;
            color: #606266;
            line-height: 1.6;
          }
        }
      }
    }

    .code-section {
      .code-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .code-language {
          font-size: 13px;
          color: #909399;
          text-transform: uppercase;
        }
      }

      .code-block {
        background-color: #282c34;
        color: #abb2bf;
        padding: 16px;
        border-radius: 6px;
        overflow-x: auto;
        font-family: 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.6;
        margin: 0;

        code {
          display: block;
          white-space: pre;
        }
      }
    }
  }

  .preview-content {
    .code-block {
      background-color: #282c34;
      color: #abb2bf;
      padding: 16px;
      border-radius: 6px;
      overflow-x: auto;
      font-family: 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.6;
      margin: 0;

      code {
        display: block;
        white-space: pre;
      }
    }
  }
}
</style>
