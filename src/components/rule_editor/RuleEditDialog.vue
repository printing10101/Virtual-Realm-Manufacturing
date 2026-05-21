<template>
  <el-dialog
    :model-value="visible"
    :title="isEditing ? '编辑工艺规则' : '新建工艺规则'"
    width="900px"
    @update:model-value="$emit('update:visible', $event)"
    @close="handleClose"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="formRules"
      label-width="100px"
    >
      <el-row :gutter="16">
        <el-col :span="16">
          <el-form-item
            label="规则名称"
            prop="name"
          >
            <el-input
              v-model="form.name"
              placeholder="请输入规则名称"
            />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="分组">
            <el-select
              v-model="form.group_id"
              placeholder="选择分组"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="g in ruleStore.groups"
                :key="g.id"
                :label="g.name"
                :value="g.id"
              />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="规则描述">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="2"
          placeholder="请输入规则描述（可选）"
        />
      </el-form-item>

      <el-form-item label="逻辑关系">
        <el-radio-group
          v-model="form.logic_operator"
          @change="updatePreview"
        >
          <el-radio-button label="AND">
            AND（全部满足）
          </el-radio-button>
          <el-radio-button label="OR">
            OR（任一满足）
          </el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="条件项">
        <div class="conditions-container">
          <el-table
            :data="form.conditions"
            border
            size="small"
          >
            <el-table-column
              label="参数"
              width="180"
            >
              <template #default="{ row }">
                <el-select
                  v-model="row.parameter"
                  placeholder="选择参数"
                  @change="updatePreview"
                >
                  <el-option-group label="材料相关">
                    <el-option
                      label="材料"
                      value="材料"
                    />
                    <el-option
                      label="材料硬度"
                      value="材料硬度"
                    />
                  </el-option-group>
                  <el-option-group label="工序相关">
                    <el-option
                      label="工序"
                      value="工序"
                    />
                    <el-option
                      label="加工精度"
                      value="加工精度"
                    />
                    <el-option
                      label="表面粗糙度"
                      value="表面粗糙度"
                    />
                  </el-option-group>
                  <el-option-group label="刀具相关">
                    <el-option
                      label="刀具类型"
                      value="刀具类型"
                    />
                    <el-option
                      label="刀具直径"
                      value="刀具直径"
                    />
                  </el-option-group>
                  <el-option-group label="切削参数">
                    <el-option
                      label="切削速度"
                      value="切削速度"
                    />
                    <el-option
                      label="进给量"
                      value="进给量"
                    />
                    <el-option
                      label="切深"
                      value="切深"
                    />
                    <el-option
                      label="切宽"
                      value="切宽"
                    />
                    <el-option
                      label="主轴转速"
                      value="主轴转速"
                    />
                  </el-option-group>
                </el-select>
              </template>
            </el-table-column>
            <el-table-column
              label="运算符"
              width="110"
            >
              <template #default="{ row }">
                <el-select
                  v-model="row.operator"
                  @change="updatePreview"
                >
                  <el-option
                    label="="
                    value="="
                  />
                  <el-option
                    label="<"
                    value="<"
                  />
                  <el-option
                    label=">"
                    value=">"
                  />
                  <el-option
                    label="<="
                    value="<="
                  />
                  <el-option
                    label=">="
                    value=">="
                  />
                  <el-option
                    label="!="
                    value="!="
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column
              label="值"
              width="140"
            >
              <template #default="{ row }">
                <el-input
                  v-model="row.value"
                  placeholder="输入值"
                  @input="updatePreview"
                />
              </template>
            </el-table-column>
            <el-table-column
              label="单位"
              width="100"
            >
              <template #default="{ row }">
                <el-select
                  v-model="row.unit"
                  placeholder="无"
                  clearable
                  @change="updatePreview"
                >
                  <el-option
                    label="mm"
                    value="mm"
                  />
                  <el-option
                    label="m/min"
                    value="m/min"
                  />
                  <el-option
                    label="mm/rev"
                    value="mm/rev"
                  />
                  <el-option
                    label="rpm"
                    value="rpm"
                  />
                  <el-option
                    label="HB"
                    value="HB"
                  />
                  <el-option
                    label="μm"
                    value="μm"
                  />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column
              label="操作"
              width="80"
            >
              <template #default="{ $index }">
                <el-button
                  size="small"
                  type="danger"
                  link
                  :disabled="form.conditions.length <= 1"
                  @click="removeCondition($index)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button
            size="small"
            type="primary"
            style="margin-top: 8px"
            @click="addCondition"
          >
            <el-icon><Plus /></el-icon>
            添加条件
          </el-button>
        </div>
      </el-form-item>

      <el-form-item
        label="结果"
        prop="result"
      >
        <el-row
          :gutter="8"
          style="width: 100%"
        >
          <el-col :span="6">
            <el-select
              v-model="form.result.parameter"
              placeholder="结果参数"
              @change="updatePreview"
            >
              <el-option
                label="切深"
                value="切深"
              />
              <el-option
                label="切宽"
                value="切宽"
              />
              <el-option
                label="切削速度"
                value="切削速度"
              />
              <el-option
                label="进给量"
                value="进给量"
              />
              <el-option
                label="主轴转速"
                value="主轴转速"
              />
            </el-select>
          </el-col>
          <el-col :span="4">
            <el-select
              v-model="form.result.operator"
              @change="updatePreview"
            >
              <el-option
                label="="
                value="="
              />
              <el-option
                label="<="
                value="<="
              />
              <el-option
                label=">="
                value=">="
              />
              <el-option
                label="<"
                value="<"
              />
              <el-option
                label=">"
                value=">"
              />
              <el-option
                label="!="
                value="!="
              />
            </el-select>
          </el-col>
          <el-col :span="6">
            <el-input
              v-model="form.result.value"
              placeholder="结果值"
              @input="updatePreview"
            />
          </el-col>
          <el-col :span="4">
            <el-select
              v-model="form.result.unit"
              placeholder="无"
              clearable
              @change="updatePreview"
            >
              <el-option
                label="mm"
                value="mm"
              />
              <el-option
                label="m/min"
                value="m/min"
              />
              <el-option
                label="mm/rev"
                value="mm/rev"
              />
              <el-option
                label="rpm"
                value="rpm"
              />
            </el-select>
          </el-col>
        </el-row>
      </el-form-item>

      <el-form-item label="状态">
        <el-select
          v-model="form.status"
          style="width: 120px"
        >
          <el-option
            label="启用"
            value="active"
          />
          <el-option
            label="停用"
            value="inactive"
          />
          <el-option
            label="草稿"
            value="draft"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="优先级">
        <el-input-number
          v-model="form.priority"
          :min="0"
          :max="100"
        />
      </el-form-item>

      <el-form-item label="规则预览">
        <el-alert
          :title="previewText || '请完善条件以生成规则预览'"
          type="info"
          :closable="false"
          :class="{ 'preview-empty': !previewText }"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        取消
      </el-button>
      <el-button
        type="primary"
        :loading="submitting"
        @click="handleSubmit"
      >
        {{ isEditing ? '保存修改' : '创建规则' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import type { ProcessRule, RuleCondition, RuleResult, RuleCreateRequest, RuleUpdateRequest } from '@/types'
import { useRuleStore } from '@/stores/rules'
import type { FormInstance, FormRules } from 'element-plus'

const props = defineProps<{
  visible: boolean
  rule: ProcessRule | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const ruleStore = useRuleStore()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const previewText = ref('')

const defaultCondition = (): RuleCondition => ({
  parameter: '',
  operator: '=',
  value: '',
  unit: undefined,
})

const defaultResult = (): RuleResult => ({
  parameter: '',
  operator: '<=',
  value: '',
  unit: undefined,
})

const form = ref<{
  name: string
  description: string
  group_id?: number
  conditions: RuleCondition[]
  logic_operator: 'AND' | 'OR'
  result: RuleResult
  status: 'active' | 'inactive' | 'draft'
  priority: number
}>({
  name: '',
  description: '',
  group_id: undefined,
  conditions: [defaultCondition()],
  logic_operator: 'AND',
  result: defaultResult(),
  status: 'active',
  priority: 0,
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  result: [{ required: true, message: '请设置结果项', trigger: 'change' }],
}

const isEditing = computed(() => !!props.rule)

watch(
  () => props.rule,
  (newRule) => {
    if (newRule) {
      form.value = {
        name: newRule.name,
        description: newRule.description,
        group_id: newRule.group_id,
        conditions: newRule.conditions.length > 0 ? [...newRule.conditions] : [defaultCondition()],
        logic_operator: newRule.logic_operator,
        result: newRule.result ? { ...newRule.result } : defaultResult(),
        status: newRule.status,
        priority: newRule.priority,
      }
    } else {
      resetForm()
    }
    updatePreview()
  },
  { immediate: true }
)

function resetForm() {
  form.value = {
    name: '',
    description: '',
    group_id: undefined,
    conditions: [defaultCondition()],
    logic_operator: 'AND',
    result: defaultResult(),
    status: 'active',
    priority: 0,
  }
}

function addCondition() {
  form.value.conditions.push(defaultCondition())
  updatePreview()
}

function removeCondition(index: number) {
  if (form.value.conditions.length > 1) {
    form.value.conditions.splice(index, 1)
    updatePreview()
  }
}

function updatePreview() {
  const validConditions = form.value.conditions.filter((c) => c.parameter && c.value)
  if (validConditions.length === 0) {
    previewText.value = ''
    return
  }

  const condTexts = validConditions.map((c) => {
    let text = `${c.parameter} ${c.operator} ${c.value}`
    if (c.unit) text += c.unit
    return text
  })

  const condStr = condTexts.join(` ${form.value.logic_operator} `)
  let resultStr = ''
  if (form.value.result.parameter && form.value.result.value) {
    resultStr = `${form.value.result.parameter} ${form.value.result.operator} ${form.value.result.value}`
    if (form.value.result.unit) resultStr += form.value.result.unit
  }

  previewText.value = resultStr ? `IF ${condStr} THEN ${resultStr}` : `IF ${condStr}`
}

async function handleSubmit() {
  if (!formRef.value) return

  try {
    await formRef.value.validate()
  } catch {
    ElMessage.warning('请检查表单填写')
    return
  }

  const validConditions = form.value.conditions.filter((c) => c.parameter && c.value)
  if (validConditions.length === 0) {
    ElMessage.warning('请至少添加一个有效条件')
    return
  }

  if (!form.value.result.parameter || !form.value.result.value) {
    ElMessage.warning('请设置结果项')
    return
  }

  submitting.value = true
  try {
    if (isEditing.value && props.rule?.id) {
      const updateData: RuleUpdateRequest = {
        name: form.value.name,
        description: form.value.description,
        group_id: form.value.group_id,
        conditions: validConditions,
        logic_operator: form.value.logic_operator,
        result: form.value.result,
        status: form.value.status,
        priority: form.value.priority,
      }
      await ruleStore.updateRule(props.rule.id, updateData)
    } else {
      const createData: RuleCreateRequest = {
        name: form.value.name,
        description: form.value.description,
        group_id: form.value.group_id,
        conditions: validConditions,
        logic_operator: form.value.logic_operator,
        result: form.value.result,
        status: form.value.status,
        priority: form.value.priority,
      }
      await ruleStore.createRule(createData)
    }
    emit('saved')
    emit('update:visible', false)
  } catch (e) {
    console.error('规则保存失败:', e)
  } finally {
    submitting.value = false
  }
}

function handleClose() {
  resetForm()
  previewText.value = ''
}
</script>

<style scoped>
.conditions-container {
  width: 100%;
}

.preview-empty :deep(.el-alert__title) {
  color: #c0c4cc;
}
</style>
