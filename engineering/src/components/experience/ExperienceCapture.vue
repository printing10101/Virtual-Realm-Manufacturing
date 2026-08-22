<!-- 切削实测采集表单（数据飞轮手工录入入口，P2-3 前端） -->
<template>
  <div class="experience-capture">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>切削实测采集</span>
          <el-button
            type="primary"
            :loading="capturing"
            data-test="submit-btn"
            @click="handleSubmit"
          >
            提交记录
          </el-button>
        </div>
      </template>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="120px"
        size="default"
      >
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="机床" prop="machine_id">
              <el-input v-model="form.machine_id" placeholder="如 VM-001" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="刀具" prop="tool_id">
              <el-input v-model="form.tool_id" placeholder="如 T-12" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="材料">
              <el-input v-model="form.material" placeholder="如 AL6061" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="加工类型">
              <el-select v-model="form.machining_type" style="width: 100%">
                <el-option label="铣削" value="milling" />
                <el-option label="车削" value="turning" />
                <el-option label="钻孔" value="drilling" />
                <el-option label="攻丝" value="tapping" />
                <el-option label="镗孔" value="boring" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">工艺参数</el-divider>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="切深 (mm)" prop="depth_of_cut_mm">
              <el-input-number
                v-model="form.parameters.depth_of_cut_mm"
                :min="0.1"
                :step="0.1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="进给 (mm/rev)" prop="feed_mm_per_rev">
              <el-input-number
                v-model="form.parameters.feed_mm_per_rev"
                :min="0.01"
                :step="0.01"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="转速 (RPM)" prop="spindle_rpm">
              <el-input-number
                v-model="form.parameters.spindle_rpm"
                :min="1"
                :step="100"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-divider content-position="left">实测结果</el-divider>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="节拍 (s)" prop="cycle_time_s">
              <el-input-number
                v-model="form.results.cycle_time_s"
                :min="0.1"
                :step="0.5"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="粗糙度 Ra">
              <el-input-number
                v-model="form.results.surface_roughness_ra"
                :min="0"
                :step="0.1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="刀具磨损 %">
              <el-input-number
                v-model="form.results.tool_wear_percent"
                :min="0"
                :max="100"
                :step="1"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="结果判定">
              <el-radio-group v-model="form.results.result">
                <el-radio value="ok">合格</el-radio>
                <el-radio value="rework">返工</el-radio>
                <el-radio value="scrap">报废</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="操作员">
              <el-input v-model="form.operator" placeholder="选填" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-alert
        v-if="experienceStore.errorMessage"
        :title="experienceStore.errorMessage"
        type="error"
        show-icon
        closable
        @close="experienceStore.clearError()"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useExperienceStore } from '@/stores/experienceStore'
import type { CuttingExperiencePayload } from '@/api/cuttingExperience'

const experienceStore = useExperienceStore()

interface CaptureForm {
  machine_id: string
  tool_id: string
  material: string
  machining_type: string
  operator: string
  parameters: {
    depth_of_cut_mm: number
    feed_mm_per_rev: number
    spindle_rpm: number
  }
  results: {
    cycle_time_s: number
    surface_roughness_ra: number | null
    tool_wear_percent: number | null
    result: 'ok' | 'rework' | 'scrap'
  }
}

const formRef = ref<FormInstance>()
const form = reactive<CaptureForm>({
  machine_id: '',
  tool_id: '',
  material: '',
  machining_type: 'milling',
  operator: '',
  parameters: { depth_of_cut_mm: 1.0, feed_mm_per_rev: 0.2, spindle_rpm: 8000 },
  results: {
    cycle_time_s: 60,
    surface_roughness_ra: null,
    tool_wear_percent: null,
    result: 'ok',
  },
})

const rules: FormRules = {
  machine_id: [{ required: true, message: '请输入机床标识', trigger: 'blur' }],
  tool_id: [{ required: true, message: '请输入刀具标识', trigger: 'blur' }],
  depth_of_cut_mm: [{ required: true, message: '请输入切深', trigger: 'blur' }],
  feed_mm_per_rev: [{ required: true, message: '请输入进给', trigger: 'blur' }],
  spindle_rpm: [{ required: true, message: '请输入转速', trigger: 'blur' }],
  cycle_time_s: [{ required: true, message: '请输入节拍', trigger: 'blur' }],
}

const capturing = ref(false)

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  capturing.value = true
  const payload: CuttingExperiencePayload = {
    machine_id: form.machine_id,
    tool_id: form.tool_id,
    material: form.material || undefined,
    machining_type: form.machining_type as CuttingExperiencePayload['machining_type'],
    operator: form.operator || null,
    parameters: {
      depth_of_cut_mm: form.parameters.depth_of_cut_mm,
      feed_mm_per_rev: form.parameters.feed_mm_per_rev,
      spindle_rpm: form.parameters.spindle_rpm,
    },
    results: {
      cycle_time_s: form.results.cycle_time_s,
      surface_roughness_ra: form.results.surface_roughness_ra,
      tool_wear_percent: form.results.tool_wear_percent,
      result: form.results.result,
    },
  }

  const created = await experienceStore.submitCapture(payload)
  capturing.value = false
  if (created) {
    ElMessage.success(`记录已入库 (${created.id})`)
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
