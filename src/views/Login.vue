<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <h1 class="login-title">
          {{ $t('auth.loginTitle') }}
        </h1>
        <p class="login-subtitle">
          {{ $t('auth.loginSubtitle') }}
        </p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @submit.prevent="handleLogin"
      >
        <el-form-item
          :label="$t('auth.username')"
          prop="username"
        >
          <el-input
            v-model="form.username"
            :placeholder="$t('auth.usernamePlaceholder')"
            prefix-icon="User"
            size="large"
            autocomplete="username"
          />
        </el-form-item>

        <el-form-item
          :label="$t('auth.password')"
          prop="password"
        >
          <el-input
            v-model="form.password"
            type="password"
            :placeholder="$t('auth.passwordPlaceholder')"
            prefix-icon="Lock"
            size="large"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            native-type="submit"
            class="login-btn"
          >
            {{ loading ? $t('auth.loggingIn') : $t('auth.login') }}
          </el-button>
        </el-form-item>

        <div
          v-if="errorMsg"
          class="login-error"
        >
          <el-alert
            :title="errorMsg"
            type="error"
            show-icon
            :closable="false"
          />
        </div>
      </el-form>

      <div class="login-footer">
        <el-button
          link
          type="primary"
          @click="switchToRegister"
        >
          {{ isRegister ? $t('auth.haveAccount') : $t('auth.noAccount') }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { FormInstance, FormRules } from 'element-plus'
import http from '@/utils/http'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const isRegister = ref(false)
const loading = ref(false)
const errorMsg = ref('')
const formRef = ref<FormInstance>()

const form = reactive({
  username: '',
  password: '',
})

const validatePassword = (_rule: any, value: string, callback: any) => {
  if (!value) {
    callback(new Error(t('auth.passwordRequired')))
    return
  }
  if (value.length < 8) {
    callback(new Error(t('auth.passwordTooShort')))
    return
  }
  const hasLetter = /[a-zA-Z]/.test(value)
  const hasDigit = /[0-9]/.test(value)
  if (!hasLetter || !hasDigit) {
    callback(new Error(t('auth.passwordStrength')))
    return
  }
  callback()
}

const rules: FormRules = {
  username: [
    { required: true, message: t('auth.usernameRequired'), trigger: 'blur' },
  ],
  password: [
    { required: true, validator: validatePassword, trigger: 'blur' },
  ],
}

function switchToRegister() {
  isRegister.value = !isRegister.value
  errorMsg.value = ''
  formRef.value?.resetFields()
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  errorMsg.value = ''

  try {
    const endpoint = isRegister.value ? '/api/v1/auth/register' : '/api/v1/auth/login'
    const response = await http.post(endpoint, {
      username: form.username,
      password: form.password,
    })

    if (response.data?.code === 0 && response.data?.data) {
      const data = response.data.data
      if (!isRegister.value) {
        authStore.setAuth(data)
      } else {
        const loginResponse = await http.post('/api/v1/auth/login', {
          username: form.username,
          password: form.password,
        })
        if (loginResponse.data?.code === 0 && loginResponse.data?.data) {
          authStore.setAuth(loginResponse.data.data)
        }
      }
      router.push('/')
    }
  } catch (e: any) {
    const detail = e.response?.data?.detail || e.response?.data?.message || ''
    errorMsg.value = detail || t('auth.loginFailed')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
}

.login-card {
  width: 420px;
  padding: 40px;
  background: rgba(255, 255, 255, 0.05);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-title {
  font-size: 28px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 8px 0;
}

.login-subtitle {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  margin: 0;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
}

.login-error {
  margin-bottom: 16px;
}

.login-footer {
  text-align: center;
  margin-top: 16px;
}
</style>