<template>
  <slot v-if="canRender" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { usePermissionsStore } from '@/stores/permissions'
import { useAuthStore } from '@/stores/auth'

const props = withDefaults(
  defineProps<{
    permission?: string
    permissions?: string[]
    mode?: 'all' | 'any'
    role?: string
    roles?: string[]
  }>(),
  {
    mode: 'any',
  },
)

const permStore = usePermissionsStore()

const canRender = computed(() => {
  if (props.role) {
    const authStore = useAuthStore()
    if (authStore.user?.role === props.role) return true
  }

  if (props.roles && props.roles.length > 0) {
    const authStore = useAuthStore()
    if (authStore.user?.role && props.roles.includes(authStore.user.role)) return true
  }

  if (props.permission) {
    return permStore.hasPermission(props.permission)
  }

  if (props.permissions && props.permissions.length > 0) {
    return props.mode === 'all'
      ? permStore.hasAllPermissions(...props.permissions)
      : permStore.hasAnyPermission(...props.permissions)
  }

  return true
})
</script>