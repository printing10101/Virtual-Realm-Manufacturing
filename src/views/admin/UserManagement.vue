<template>
  <div class="user-management-page">
    <div class="page-header">
      <h2>用户管理</h2>
      <el-tag type="info">
        管理员专用
      </el-tag>
    </div>

    <el-card>
      <el-table
        v-loading="loading"
        :data="users"
        stripe
        border
        style="width: 100%"
      >
        <el-table-column
          prop="username"
          label="用户名"
          min-width="120"
        />
        <el-table-column
          label="角色"
          min-width="140"
        >
          <template #default="{ row }">
            <el-select
              :model-value="row.role"
              size="small"
              :disabled="row.username === currentUsername"
              @change="(val: string) => handleRoleChange(row.username, val)"
            >
              <el-option
                label="管理员"
                value="admin"
              />
              <el-option
                label="工程师"
                value="engineer"
              />
              <el-option
                label="操作员"
                value="operator"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          label="状态"
          width="100"
        >
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :disabled="row.username === currentUsername"
              active-text="启用"
              inactive-text="禁用"
              @change="(val: string | number | boolean) => handleStatusChange(row.username, Boolean(val))"
            />
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          label="创建时间"
          min-width="170"
        >
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="last_login"
          label="最后登录"
          min-width="170"
        >
          <template #default="{ row }">
            {{ formatDate(row.last_login) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '@/utils/http'
import { useAuthStore } from '@/stores/auth'
import { formatDate } from '@/utils/formatters'

interface UserItem {
  username: string
  role: string
  is_active: boolean
  created_at: string | null
  last_login: string | null
}

const authStore = useAuthStore()
const currentUsername = authStore.currentUsername

const users = ref<UserItem[]>([])
const loading = ref(false)

async function fetchUsers() {
  loading.value = true
  try {
    const res = await http.get('/api/v1/users')
    if (res.data?.code === 0 && res.data?.data) {
      users.value = res.data.data.users || []
    }
  } catch {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(username: string, newRole: string) {
  try {
    const res = await http.put(`/api/v1/users/${username}/role`, { role_code: newRole })
    if (res.data?.code === 0) {
      const user = users.value.find((u) => u.username === username)
      if (user) user.role = newRole
      ElMessage.success(`已将 ${username} 的角色修改为 ${newRole}`)
    }
  } catch {
    ElMessage.error('角色修改失败')
  }
}

async function handleStatusChange(username: string, active: boolean) {
  try {
    const res = await http.put(`/api/v1/users/${username}/status`, { is_active: active })
    if (res.data?.code === 0) {
      const user = users.value.find((u) => u.username === username)
      if (user) user.is_active = active
      const action = active ? '启用' : '禁用'
      ElMessage.success(`已${action}用户 ${username}`)
    }
  } catch {
    ElMessage.error('状态修改失败')
  }
}

onMounted(fetchUsers)
</script>

<style scoped>
.user-management-page {
  max-width: 1100px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
}
</style>