<template>
  <el-dialog
    :model-value="visible"
    title="规则分组管理"
    width="600px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
  >
    <div class="group-manager">
      <div class="group-form">
        <el-input
          v-model="groupName"
          placeholder="输入新分组名称..."
          style="width: 200px"
          @keyup.enter="handleCreate"
        />
        <el-input
          v-model="groupDesc"
          placeholder="描述（可选）..."
          style="width: 180px; margin-left: 8px"
        />
        <el-button type="primary" @click="handleCreate" style="margin-left: 8px">
          <el-icon><Plus /></el-icon>
          {{ isEditing ? '保存' : '创建' }}
        </el-button>
      </div>

      <el-table :data="ruleStore.groups" border style="margin-top: 16px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="分组名称" />
        <el-table-column prop="description" label="描述" />
        <el-table-column prop="rule_count" label="规则数" width="90" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" link @click="handleEdit(row)">编辑</el-button>
            <el-popconfirm
              :title="`确定删除分组「${row.name}」？`"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button size="small" type="danger" link :disabled="row.rule_count > 0">
                  删除
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useRuleStore } from '@/stores/rules'
import type { RuleGroup } from '@/types'

const props = defineProps<{
  visible: boolean
  group: RuleGroup | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const ruleStore = useRuleStore()
const groupName = ref('')
const groupDesc = ref('')
const isEditing = ref(false)

watch(
  () => props.group,
  (newGroup) => {
    if (newGroup) {
      groupName.value = newGroup.name
      groupDesc.value = newGroup.description
      isEditing.value = true
    } else {
      groupName.value = ''
      groupDesc.value = ''
      isEditing.value = false
    }
  },
  { immediate: true }
)

async function handleCreate() {
  if (!groupName.value.trim()) {
    ElMessage.warning('请输入分组名称')
    return
  }

  try {
    if (isEditing.value && props.group?.id) {
      await ruleStore.updateGroup(props.group.id, {
        name: groupName.value,
        description: groupDesc.value,
      })
    } else {
      await ruleStore.createGroup({
        name: groupName.value,
        description: groupDesc.value,
      })
    }
    groupName.value = ''
    groupDesc.value = ''
    isEditing.value = false
    emit('saved')
  } catch (e) {
    console.error('分组保存失败:', e)
  }
}

function handleEdit(group: RuleGroup) {
  groupName.value = group.name
  groupDesc.value = group.description
  isEditing.value = true
}

async function handleDelete(groupId?: number) {
  if (!groupId) return
  await ruleStore.deleteGroup(groupId)
}

function handleClose() {
  groupName.value = ''
  groupDesc.value = ''
  isEditing.value = false
}
</script>

<style scoped>
.group-form {
  display: flex;
  align-items: center;
}
</style>
