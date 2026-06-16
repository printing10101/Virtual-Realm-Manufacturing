import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import StepCard from '../StepCard.vue'
import type { ReasoningStep } from '@/api/reasoning'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  CircleCheck: { name: 'CircleCheck', template: '<i />' },
  CircleClose: { name: 'CircleClose', template: '<i />' },
  Promotion: { name: 'Promotion', template: '<i />' },
  Check: { name: 'Check', template: '<i />' },
  TrendCharts: { name: 'TrendCharts', template: '<i />' },
  Star: { name: 'Star', template: '<i />' },
}))

const globalStubs = {
  ElTag: {
    name: 'ElTag',
    template: '<div class="el-tag"><slot /></div>',
    props: ['type', 'size', 'effect'],
  },
  ElIcon: {
    name: 'ElIcon',
    template: '<div class="el-icon"><slot /></div>',
    props: ['size'],
  },
  ElProgress: {
    name: 'ElProgress',
    template: '<div class="el-progress" :data-percentage="percentage"></div>',
    props: ['percentage', 'strokeWidth', 'showText', 'color'],
  },
  ElTable: {
    name: 'ElTable',
    template: '<table class="el-table"><slot /></table>',
    props: ['data', 'size', 'border'],
  },
  ElTableColumn: {
    name: 'ElTableColumn',
    template: '<td class="el-table-column"></td>',
    props: ['prop', 'label', 'width'],
  },
}

describe('StepCard.vue', () => {
  let wrapper: VueWrapper<any>

  const baseStep: ReasoningStep = {
    id: 'step-1',
    type: 'task_routing',
    title: '任务路由决策',
    status: 'completed',
    timestamp: Date.now(),
    duration: 120,
    confidence: 0.85,
    evidence: {
      summary: '基于工件特征匹配到合适的加工策略',
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('组件渲染', () => {
    it('应该正确挂载组件', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.exists()).toBe(true)
    })

    it('应该显示步骤标题', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-title').text()).toBe('任务路由决策')
    })

    it('应该显示步骤耗时', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-duration').text()).toContain('120ms')
    })

    it('没有耗时时不显示耗时区域', () => {
      const step = { ...baseStep, duration: undefined }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-duration').exists()).toBe(false)
    })
  })

  describe('状态标签', () => {
    it('completed 状态应显示"已完成"', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-status').text()).toContain('已完成')
    })

    it('running 状态应显示"执行中"', () => {
      const step = { ...baseStep, status: 'running' as const }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-status').text()).toContain('执行中')
    })

    it('failed 状态应显示"失败"', () => {
      const step = { ...baseStep, status: 'failed' as const }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-status').text()).toContain('失败')
    })

    it('pending 状态应显示"待执行"', () => {
      const step = { ...baseStep, status: 'pending' as const }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-status').text()).toContain('待执行')
    })

    it('skipped 状态应显示"已跳过"', () => {
      const step = { ...baseStep, status: 'skipped' as const }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-status').text()).toContain('已跳过')
    })
  })

  describe('样式类', () => {
    it('应该有正确的类型和状态类', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-card').classes()).toContain('step-task_routing')
      expect(wrapper.find('.step-card').classes()).toContain('status-completed')
    })
  })

  describe('任务路由依据', () => {
    it('有匹配规则时应显示规则列表', () => {
      const step: ReasoningStep = {
        ...baseStep,
        evidence: {
          summary: '路由匹配',
          routingRules: [
            { rule: '材料=铝合金', matched: true, description: '匹配材料类型' },
            { rule: '精度=高', matched: false, description: '精度要求' },
          ],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      const rules = wrapper.findAll('.rule-item')
      expect(rules.length).toBe(2)
      expect(rules[0].classes()).toContain('matched')
      expect(rules[1].classes()).not.toContain('matched')
    })

    it('有相似案例时应显示案例列表', () => {
      const step: ReasoningStep = {
        ...baseStep,
        evidence: {
          summary: '路由匹配',
          similarCases: [
            { taskId: 'TASK-001', similarity: 0.92, result: '成功' },
            { taskId: 'TASK-002', similarity: 0.78, result: '成功' },
          ],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      const cases = wrapper.findAll('.case-item')
      expect(cases.length).toBe(2)
      expect(cases[0].find('.case-id').text()).toBe('TASK-001')
    })
  })

  describe('物理校验依据', () => {
    it('physical_validation 类型应显示校验参数表格', () => {
      const step: ReasoningStep = {
        ...baseStep,
        type: 'physical_validation',
        evidence: {
          summary: '物理校验通过',
          validationParams: [
            { name: '切削力', value: 250, unit: 'N', threshold: 500, passed: true },
          ],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.evidence-section').exists()).toBe(true)
      expect(wrapper.find('.el-table').exists()).toBe(true)
    })

    it('有物理公式时应显示公式列表', () => {
      const step: ReasoningStep = {
        ...baseStep,
        type: 'physical_validation',
        evidence: {
          summary: '物理校验',
          physicsFormulas: ['F = ma', 'P = Fv'],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      const formulas = wrapper.findAll('.formula-list code')
      expect(formulas.length).toBe(2)
    })
  })

  describe('主动学习依据', () => {
    it('active_learning 类型应显示学习曲线信息', () => {
      const step: ReasoningStep = {
        ...baseStep,
        type: 'active_learning',
        evidence: {
          summary: '主动学习分析',
          learningCurve: [
            { epoch: 1, loss: 0.5, accuracy: 0.6 },
            { epoch: 2, loss: 0.3, accuracy: 0.75 },
            { epoch: 3, loss: 0.15, accuracy: 0.88 },
          ],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      const curveInfo = wrapper.find('.curve-info')
      expect(curveInfo.exists()).toBe(true)
      expect(curveInfo.text()).toContain('Epoch: 3')
      expect(curveInfo.text()).toContain('0.1500')
    })

    it('有样本对比时应显示样本列表', () => {
      const step: ReasoningStep = {
        ...baseStep,
        type: 'active_learning',
        evidence: {
          summary: '主动学习分析',
          sampleComparison: [
            { source: '训练集', label: '正常', features: [1, 2, 3] },
            { source: '测试集', label: '异常', features: [4, 5] },
          ],
        },
      }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      const samples = wrapper.findAll('.sample-item')
      expect(samples.length).toBe(2)
      expect(samples[0].find('.sample-source').text()).toBe('训练集')
    })
  })

  describe('置信度展示', () => {
    it('有置信度时应显示置信度区域', () => {
      wrapper = mount(StepCard, { props: { step: baseStep }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-confidence').exists()).toBe(true)
    })

    it('没有置信度时不应显示置信度区域', () => {
      const step = { ...baseStep, confidence: undefined }
      wrapper = mount(StepCard, { props: { step }, global: { stubs: globalStubs } })
      expect(wrapper.find('.step-confidence').exists()).toBe(false)
    })
  })
})
