<template>
  <div class="user-management-page">
    <div class="page-header">
      <h2>{{ $t('userManagement.pageTitle') }}</h2>
      <el-tag type="info">
        {{ $t('userManagement.adminOnly') }}
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
          :label="$t('userManagement.colUsername')"
          min-width="120"
        />
        <el-table-column
          :label="$t('userManagement.colRole')"
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
                :label="$t('userManagement.roleAdmin')"
                value="admin"
              />
              <el-option
                :label="$t('userManagement.roleEngineer')"
                value="engineer"
              />
              <el-option
                :label="$t('userManagement.roleOperator')"
                value="operator"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('userManagement.colStatus')"
          width="100"
        >
          <template #default="{ row }">
            <el-switch
              :model-value="row.is_active"
              :disabled="row.username === currentUsername"
              :active-text="$t('userManagement.activeText')"
              :inactive-text="$t('userManagement.inactiveText')"
              @change="(val: string | number | boolean) => handleStatusChange(row.username, Boolean(val))"
            />
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          :label="$t('userManagement.colCreatedAt')"
          min-width="170"
        >
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="last_login"
          :label="$t('userManagement.colLastLogin')"
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
import { useI18n } from 'vue-i18n'
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

const { t } = useI18n()
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
    ElMessage.error(t('userManagement.loadFailed'))
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
      ElMessage.success(t('userManagement.roleChangeSuccess', { username, role: newRole }))
    }
  } catch {
    ElMessage.error(t('userManagement.roleChangeFailed'))
  }
}

async function handleStatusChange(username: string, active: boolean) {
  try {
    const res = await http.put(`/api/v1/users/${username}/status`, { is_active: active })
    if (res.data?.code === 0) {
      const user = users.value.find((u) => u.username === username)
      if (user) user.is_active = active
      const action = active
        ? t('userManagement.statusActionEnable')
        : t('userManagement.statusActionDisable')
      ElMessage.success(t('userManagement.statusChangeSuccess', { username, action }))
    }
  } catch {
    ElMessage.error(t('userManagement.statusChangeFailed'))
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