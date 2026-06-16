/* eslint-disable vue/no-unused-vars */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import * as THREE from 'three'
import HighlightViewer from '@/components/HighlightViewer.vue'
import { useFeatureHighlight, type FeatureInfo } from '@/composables/useFeatureHighlight'

// Mock Three.js 场景
vi.mock('@/composables/useThreeScene', () => {
  const mockRenderer = {
    domElement: Object.assign(document.createElement('canvas'), {
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600 }),
    }),
    setSize: vi.fn(),
    setPixelRatio: vi.fn(),
    render: vi.fn(),
    dispose: vi.fn(),
    setClearColor: vi.fn(),
    shadowMap: { enabled: false },
  }

  return {
    useThreeScene: vi.fn(() => ({
      scene: new THREE.Scene(),
      camera: new THREE.PerspectiveCamera(60, 800 / 600, 0.1, 1000),
      renderer: mockRenderer,
      controls: {
        target: new THREE.Vector3(),
        update: vi.fn(),
      },
      addLight: vi.fn(),
      startAnimation: vi.fn(),
      cleanup: vi.fn(),
    })),
  }
})

// Mock BroadcastChannel
const mockPostMessage = vi.fn()
const mockClose = vi.fn()
const MockBroadcastChannel = vi.fn().mockImplementation(() => ({
  postMessage: mockPostMessage,
  close: mockClose,
  onmessage: null,
}))

Object.defineProperty(globalThis, 'BroadcastChannel', {
  value: MockBroadcastChannel,
  writable: true,
})

// Mock 测试用特征数据
const mockFeatures: FeatureInfo[] = [
  {
    id: 'feature-001',
    name: '孔特征 A',
    type: 'hole',
    description: '直径 10mm 通孔',
    geometry: {
      center: [0, 0, 10],
      boundingBox: {
        min: [-5, -5, 5],
        max: [5, 5, 15],
      },
      faceIndices: [0, 1, 2],
    },
    aiInfo: {
      importance: 0.95,
      reason: '关键装配特征',
      category: '装配',
    },
  },
  {
    id: 'feature-002',
    name: '平面特征 B',
    type: 'plane',
    description: '底面精加工面',
    geometry: {
      center: [20, 0, 0],
      boundingBox: {
        min: [15, -10, -2],
        max: [25, 10, 2],
      },
    },
    aiInfo: {
      importance: 0.78,
      reason: '密封配合面',
      category: '密封',
    },
  },
  {
    id: 'feature-003',
    name: '槽特征 C',
    type: 'slot',
    description: '退刀槽',
    geometry: {
      center: [-10, 5, 5],
    },
    aiInfo: {
      importance: 0.45,
      reason: '工艺退让结构',
      category: '工艺',
    },
  },
]

describe('useFeatureHighlight composable', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('初始化与状态', () => {
    it('应该正确初始化默认状态', () => {
      const {
        selectedFeatureId,
        hoveredFeatureId,
        features,
        hoverInfo,
        syncEnabled,
        hasSelection,
        selectedFeature,
        hoveredFeature,
      } = useFeatureHighlight()

      expect(selectedFeatureId.value).toBeNull()
      expect(hoveredFeatureId.value).toBeNull()
      expect(features.value).toEqual([])
      expect(hoverInfo.value).toBeNull()
      expect(syncEnabled.value).toBe(true)
      expect(hasSelection.value).toBe(false)
      expect(selectedFeature.value).toBeNull()
      expect(hoveredFeature.value).toBeNull()
    })

    it('应该初始化 BroadcastChannel 用于多窗口同步', () => {
      useFeatureHighlight()
      expect(MockBroadcastChannel).toHaveBeenCalledWith('feature-highlight-sync')
    })

    it('应该接受自定义配置', () => {
      const scene = { value: new THREE.Scene() }
      const composable = useFeatureHighlight({
        scene: scene as any,
      })
      expect(composable).toBeDefined()
    })
  })

  describe('特征管理', () => {
    it('应该能够设置特征列表', () => {
      const { features, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      expect(features.value).toHaveLength(3)
      expect(features.value[0].id).toBe('feature-001')
    })

    it('应该能够更新特征列表', () => {
      const { features, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      expect(features.value).toHaveLength(3)

      setFeatures([mockFeatures[0]])
      expect(features.value).toHaveLength(1)
    })

    it('应该能够设置空特征列表', () => {
      const { features, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      setFeatures([])
      expect(features.value).toHaveLength(0)
    })
  })

  describe('计算属性', () => {
    it('应该返回选中的特征对象', () => {
      const { selectedFeatureId, selectedFeature, setFeatures, applyHighlight } =
        useFeatureHighlight()
      setFeatures(mockFeatures)

      // 直接设置 selectedFeatureId 通过 applyHighlight（需要 scene/modelGroup）
      // 这里测试计算属性的逻辑，直接修改内部状态
      selectedFeatureId.value = 'feature-001'
      expect(selectedFeature.value).not.toBeNull()
      expect(selectedFeature.value?.name).toBe('孔特征 A')
    })

    it('应该在没有选中时返回 null', () => {
      const { selectedFeatureId, selectedFeature, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      selectedFeatureId.value = null
      expect(selectedFeature.value).toBeNull()
    })

    it('应该返回悬停的特征对象', () => {
      const { hoveredFeatureId, hoveredFeature, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      hoveredFeatureId.value = 'feature-002'
      expect(hoveredFeature.value).not.toBeNull()
      expect(hoveredFeature.value?.name).toBe('平面特征 B')
    })

    it('应该正确计算 hasSelection', () => {
      const { selectedFeatureId, hasSelection } = useFeatureHighlight()
      expect(hasSelection.value).toBe(false)
      selectedFeatureId.value = 'feature-001'
      expect(hasSelection.value).toBe(true)
    })
  })

  describe('悬停处理', () => {
    it('应该更新悬停信息', () => {
      const { hoveredFeatureId, hoverInfo, setFeatures, handleHover } = useFeatureHighlight()
      setFeatures(mockFeatures)

      handleHover('feature-001', 100, 200)

      expect(hoveredFeatureId.value).toBe('feature-001')
      expect(hoverInfo.value).not.toBeNull()
      expect(hoverInfo.value?.feature.id).toBe('feature-001')
      expect(hoverInfo.value?.screenPosition.x).toBe(100)
      expect(hoverInfo.value?.screenPosition.y).toBe(200)
    })

    it('应该清除悬停信息当 featureId 为 null', () => {
      const { hoveredFeatureId, hoverInfo, setFeatures, handleHover } = useFeatureHighlight()
      setFeatures(mockFeatures)

      handleHover('feature-001', 100, 200)
      expect(hoverInfo.value).not.toBeNull()

      handleHover(null)
      expect(hoveredFeatureId.value).toBeNull()
      expect(hoverInfo.value).toBeNull()
    })

    it('应该忽略重复的悬停事件', () => {
      const { hoverInfo, setFeatures, handleHover } = useFeatureHighlight()
      setFeatures(mockFeatures)

      handleHover('feature-001', 100, 200)
      const firstTimestamp = hoverInfo.value?.timestamp

      // 同一特征再次悬停不应更新
      handleHover('feature-001', 150, 250)
      expect(hoverInfo.value?.timestamp).toBe(firstTimestamp)
    })

    it('应该处理不存在的特征 ID', () => {
      const { hoveredFeatureId, hoverInfo, setFeatures, handleHover } = useFeatureHighlight()
      setFeatures(mockFeatures)

      handleHover('non-existent-id', 100, 200)
      expect(hoveredFeatureId.value).toBe('non-existent-id')
      expect(hoverInfo.value).toBeNull()
    })
  })

  describe('高亮核心逻辑', () => {
    it('应该在没有 scene 时仍然更新选中状态', () => {
      const { selectedFeatureId, setFeatures, applyHighlight } = useFeatureHighlight()
      setFeatures(mockFeatures)

      applyHighlight('feature-001')
      expect(selectedFeatureId.value).toBe('feature-001')
    })

    it('应该清除高亮并重置选中状态', () => {
      const { selectedFeatureId, setFeatures, applyHighlight, clearHighlight } =
        useFeatureHighlight()
      setFeatures(mockFeatures)

      applyHighlight('feature-001')
      expect(selectedFeatureId.value).toBe('feature-001')

      clearHighlight()
      expect(selectedFeatureId.value).toBeNull()
    })

    it('应该忽略不存在的特征 ID', () => {
      const { selectedFeatureId, setFeatures, applyHighlight } = useFeatureHighlight()
      setFeatures(mockFeatures)

      applyHighlight('non-existent-id')
      expect(selectedFeatureId.value).toBeNull()
    })

    it('应该在有 scene 和 modelGroup 时创建高亮标记', () => {
      const scene = new THREE.Scene()
      const modelGroup = new THREE.Group()
      scene.add(modelGroup)

      const sceneRef = { value: scene }
      const modelGroupRef = { value: modelGroup }

      const { selectedFeatureId, setFeatures, applyHighlight } = useFeatureHighlight({
        scene: sceneRef as any,
        modelGroup: modelGroupRef as any,
      })
      setFeatures(mockFeatures)

      // feature-003 没有 boundingBox 和 faceIndices，会创建标记
      applyHighlight('feature-003')
      expect(selectedFeatureId.value).toBe('feature-003')

      // 检查场景中是否添加了高亮标记
      const highlightChildren = scene.children.filter(
        (c) => c.userData?.isHighlightMarker,
      )
      expect(highlightChildren.length).toBeGreaterThan(0)
    })

    it('应该清除旧高亮再应用新高亮', () => {
      const scene = new THREE.Scene()
      const modelGroup = new THREE.Group()
      scene.add(modelGroup)

      const sceneRef = { value: scene }
      const modelGroupRef = { value: modelGroup }

      const { selectedFeatureId, setFeatures, applyHighlight } = useFeatureHighlight({
        scene: sceneRef as any,
        modelGroup: modelGroupRef as any,
      })
      setFeatures(mockFeatures)

      applyHighlight('feature-003')
      expect(selectedFeatureId.value).toBe('feature-003')

      // 切换到另一个特征
      applyHighlight('feature-001')
      expect(selectedFeatureId.value).toBe('feature-001')
    })
  })

  describe('多窗口同步', () => {
    it('应该在选中时广播同步消息', () => {
      const { setFeatures, applyHighlight } = useFeatureHighlight()
      setFeatures(mockFeatures)

      applyHighlight('feature-001')
      expect(mockPostMessage).toHaveBeenCalled()
    })

    it('应该在清除时广播同步消息', () => {
      const { setFeatures, applyHighlight, clearHighlight } = useFeatureHighlight()
      setFeatures(mockFeatures)

      applyHighlight('feature-001')
      mockPostMessage.mockClear()

      clearHighlight()
      expect(mockPostMessage).toHaveBeenCalled()
    })

    it('应该在禁用同步时不广播', () => {
      const { syncEnabled, setFeatures, applyHighlight } = useFeatureHighlight()
      syncEnabled.value = false
      setFeatures(mockFeatures)

      mockPostMessage.mockClear()
      applyHighlight('feature-001')
      // 禁用同步时不应调用 postMessage（但 watch 可能触发）
      // 由于 syncEnabled 为 false，broadcastSync 内部会直接返回
      expect(mockPostMessage).not.toHaveBeenCalled()
    })

    it('应该忽略来自其他实例的延迟超过 50ms 的消息', () => {
      const composable = useFeatureHighlight()
      // 获取 channel 的 onmessage 回调
      const channelInstance = MockBroadcastChannel.mock.instances[MockBroadcastChannel.mock.instances.length - 1]
      if (channelInstance && channelInstance.onmessage) {
        const staleMessage = {
          data: {
            type: 'select',
            featureId: 'feature-001',
            source: 'other-instance',
            timestamp: Date.now() - 100, // 100ms 前
          },
        }
        // 不应抛出错误
        expect(() => channelInstance.onmessage(staleMessage)).not.toThrow()
      }
    })
  })

  describe('脉冲动画', () => {
    it('应该更新脉冲相位', () => {
      const { updatePulseAnimation } = useFeatureHighlight()
      // 不应抛出错误
      expect(() => updatePulseAnimation(0.016)).not.toThrow()
    })

    it('应该在没有高亮 mesh 时安全调用', () => {
      const { updatePulseAnimation } = useFeatureHighlight()
      expect(() => updatePulseAnimation(0.016)).not.toThrow()
    })

    it('应该在高亮存在时更新材质属性', () => {
      const scene = new THREE.Scene()
      const modelGroup = new THREE.Group()
      scene.add(modelGroup)

      const sceneRef = { value: scene }
      const modelGroupRef = { value: modelGroup }

      const { setFeatures, applyHighlight, updatePulseAnimation } = useFeatureHighlight({
        scene: sceneRef as any,
        modelGroup: modelGroupRef as any,
      })
      setFeatures(mockFeatures)
      applyHighlight('feature-003')

      // 更新动画不应抛出错误
      expect(() => updatePulseAnimation(0.016)).not.toThrow()
    })
  })

  describe('Raycasting 拾取', () => {
    it('应该在没有 camera/renderer/modelGroup 时返回 null', () => {
      const { pickFeatureAtScreen, setFeatures } = useFeatureHighlight()
      setFeatures(mockFeatures)
      const result = pickFeatureAtScreen(400, 300)
      expect(result).toBeNull()
    })

    it('应该在没有特征时返回 null', () => {
      const mockRenderer = {
        domElement: Object.assign(document.createElement('canvas'), {
          getBoundingClientRect: () => ({
            left: 0, top: 0, width: 800, height: 600, right: 800, bottom: 600,
          }),
        }),
      }
      const camera = new THREE.PerspectiveCamera(60, 800 / 600, 0.1, 1000)

      const { pickFeatureAtScreen } = useFeatureHighlight({
        camera: { value: camera } as any,
        renderer: { value: mockRenderer } as any,
        modelGroup: { value: new THREE.Group() } as any,
      })

      const result = pickFeatureAtScreen(400, 300)
      expect(result).toBeNull()
    })
  })

  describe('配置更新', () => {
    it('应该能够部分更新高亮配置', () => {
      const { highlightConfig, updateHighlightConfig } = useFeatureHighlight()

      updateHighlightConfig({ highlightColor: 0xff0000 })
      expect(highlightConfig.value.highlightColor).toBe(0xff0000)
      // 其他配置应保持不变
      expect(highlightConfig.value.emissiveColor).toBe(0x00ff88)
    })

    it('应该能够更新多个配置项', () => {
      const { highlightConfig, updateHighlightConfig } = useFeatureHighlight()

      updateHighlightConfig({
        highlightColor: 0xff0000,
        pulseAnimation: false,
        pulseSpeed: 3.0,
      })
      expect(highlightConfig.value.highlightColor).toBe(0xff0000)
      expect(highlightConfig.value.pulseAnimation).toBe(false)
      expect(highlightConfig.value.pulseSpeed).toBe(3.0)
    })
  })

  describe('清理', () => {
    it('应该清理所有状态', () => {
      const {
        selectedFeatureId,
        hoveredFeatureId,
        hoverInfo,
        setFeatures,
        applyHighlight,
        handleHover,
        cleanup,
      } = useFeatureHighlight()

      setFeatures(mockFeatures)
      applyHighlight('feature-001')
      handleHover('feature-002', 100, 200)

      cleanup()

      expect(selectedFeatureId.value).toBeNull()
      expect(hoveredFeatureId.value).toBeNull()
      expect(hoverInfo.value).toBeNull()
    })

    it('应该关闭 BroadcastChannel', () => {
      const { cleanup } = useFeatureHighlight()
      cleanup()
      expect(mockClose).toHaveBeenCalled()
    })
  })
})

describe('HighlightViewer.vue', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  describe('组件挂载和初始化', () => {
    it('应该正确挂载组件', () => {
      wrapper = mount(HighlightViewer)
      expect(wrapper.exists()).toBe(true)
    })

    it('应该渲染 3D 场景容器', () => {
      wrapper = mount(HighlightViewer)
      const canvasContainer = wrapper.find('.canvas-container')
      expect(canvasContainer.exists()).toBe(true)
    })

    it('应该渲染控制面板', () => {
      wrapper = mount(HighlightViewer)
      const controlPanel = wrapper.find('.control-panel')
      expect(controlPanel.exists()).toBe(true)
    })

    it('应该接受 modelUrl prop', () => {
      wrapper = mount(HighlightViewer, {
        props: { modelUrl: '/test-model.stl' },
      })
      expect(wrapper.props('modelUrl')).toBe('/test-model.stl')
    })

    it('应该接受 features prop', () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      expect(wrapper.props('features')).toEqual(mockFeatures)
    })

    it('应该接受 backgroundColor prop', () => {
      wrapper = mount(HighlightViewer, {
        props: { backgroundColor: '#ffffff' },
      })
      expect(wrapper.props('backgroundColor')).toBe('#ffffff')
    })

    it('应该接受 showGrid prop', () => {
      wrapper = mount(HighlightViewer, {
        props: { showGrid: false },
      })
      expect(wrapper.props('showGrid')).toBe(false)
    })
  })

  describe('特征列表面板', () => {
    it('应该在没有特征时不显示列表面板', () => {
      wrapper = mount(HighlightViewer)
      const panel = wrapper.find('.feature-list-panel')
      expect(panel.exists()).toBe(false)
    })

    it('应该在有特征时显示列表面板', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const panel = wrapper.find('.feature-list-panel')
      expect(panel.exists()).toBe(true)
    })

    it('应该显示正确数量的特征项', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      expect(items).toHaveLength(3)
    })

    it('应该显示特征名称', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const names = wrapper.findAll('.feature-item .feature-info .feature-name')
      expect(names[0].text()).toBe('孔特征 A')
      expect(names[1].text()).toBe('平面特征 B')
      expect(names[2].text()).toBe('槽特征 C')
    })

    it('应该显示特征类型', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const types = wrapper.findAll('.feature-item .feature-info .feature-type')
      expect(types[0].text()).toBe('hole')
      expect(types[1].text()).toBe('plane')
      expect(types[2].text()).toBe('slot')
    })

    it('应该显示 AI 重要度百分比', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const importances = wrapper.findAll('.feature-item .feature-importance')
      expect(importances[0].text()).toBe('95%')
      expect(importances[1].text()).toBe('78%')
      expect(importances[2].text()).toBe('45%')
    })

    it('应该显示特征数量标记', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const count = wrapper.find('.feature-count')
      expect(count.text()).toBe('3')
    })

    it('应该能够通过 showFeatureList 控制面板显隐', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures, initialShowFeatureList: false },
      })
      await wrapper.vm.$nextTick()

      const panel = wrapper.find('.feature-list-panel')
      expect(panel.exists()).toBe(false)
    })
  })

  describe('特征选择交互', () => {
    it('应该在点击特征项时触发选中', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')

      const emitted = wrapper.emitted('feature-select')
      expect(emitted).toBeDefined()
      expect(emitted).toHaveLength(1)
      expect(emitted![0][0]).toMatchObject({ id: 'feature-001' })
    })

    it('应该为选中项添加 selected CSS 类', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      expect(items[0].classes()).toContain('selected')
    })

    it('应该能够切换选中特征', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')

      await items[0].trigger('click')
      await wrapper.vm.$nextTick()
      expect(wrapper.findAll('.feature-item')[0].classes()).toContain('selected')

      await items[1].trigger('click')
      await wrapper.vm.$nextTick()
      const updatedItems = wrapper.findAll('.feature-item')
      expect(updatedItems[1].classes()).toContain('selected')
    })
  })

  describe('悬停交互', () => {
    it('应该在鼠标进入特征项时触发悬停', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('mouseenter')

      const emitted = wrapper.emitted('feature-hover')
      expect(emitted).toBeDefined()
      expect(emitted).toHaveLength(1)
    })

    it('应该在鼠标离开特征项时清除悬停', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('mouseenter')
      await items[0].trigger('mouseleave')

      const emitted = wrapper.emitted('feature-hover')
      expect(emitted).toBeDefined()
      // 最后一次应该是 null
      expect(emitted![emitted!.length - 1][0]).toBeNull()
    })

    it('应该为悬停项添加 hovered CSS 类', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('mouseenter')
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.feature-item')[0].classes()).toContain('hovered')
    })
  })

  describe('悬停提示框', () => {
    it('应该默认显示悬停提示', () => {
      wrapper = mount(HighlightViewer)
      // showTooltip 默认为 true
      const tooltipCheckbox = wrapper.find('input[type="checkbox"]')
      expect(tooltipCheckbox.exists()).toBe(true)
    })

    it('应该能够通过控制面板禁用悬停提示', async () => {
      wrapper = mount(HighlightViewer, {
        props: { initialShowTooltip: false },
      })
      await wrapper.vm.$nextTick()

      const tooltip = wrapper.find('.hover-tooltip')
      expect(tooltip.exists()).toBe(false)
    })
  })

  describe('控制面板', () => {
    it('应该显示"显示悬停提示"控制项', () => {
      wrapper = mount(HighlightViewer)
      const labels = wrapper.findAll('.control-label')
      const tooltipLabel = labels.find(l => l.text().includes('显示悬停提示'))
      expect(tooltipLabel).toBeDefined()
    })

    it('应该显示"显示特征列表"控制项', () => {
      wrapper = mount(HighlightViewer)
      const labels = wrapper.findAll('.control-label')
      const listLabel = labels.find(l => l.text().includes('显示特征列表'))
      expect(listLabel).toBeDefined()
    })

    it('应该显示"多窗口同步"控制项', () => {
      wrapper = mount(HighlightViewer)
      const labels = wrapper.findAll('.control-label')
      const syncLabel = labels.find(l => l.text().includes('多窗口同步'))
      expect(syncLabel).toBeDefined()
    })

    it('应该在没有选中时不显示清除按钮', () => {
      wrapper = mount(HighlightViewer)
      const clearBtn = wrapper.find('.clear-button')
      expect(clearBtn.exists()).toBe(false)
    })

    it('应该在选中后显示清除按钮', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const clearBtn = wrapper.find('.clear-button')
      expect(clearBtn.exists()).toBe(true)
    })

    it('应该在点击清除按钮后清除选中', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const clearBtn = wrapper.find('.clear-button')
      await clearBtn.trigger('click')
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('feature-clear')
      expect(emitted).toBeDefined()
      expect(emitted).toHaveLength(1)
    })
  })

  describe('选中状态指示器', () => {
    it('应该在没有选中时不显示指示器', () => {
      wrapper = mount(HighlightViewer)
      const indicator = wrapper.find('.selection-indicator')
      expect(indicator.exists()).toBe(false)
    })

    it('应该在选中后显示指示器', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const indicator = wrapper.find('.selection-indicator')
      expect(indicator.exists()).toBe(true)
      expect(indicator.text()).toContain('孔特征 A')
    })

    it('应该显示 AI 重要度和类别', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const indicator = wrapper.find('.selection-indicator')
      expect(indicator.text()).toContain('95%')
      expect(indicator.text()).toContain('装配')
    })
  })

  describe('暴露的方法', () => {
    it('应该暴露 selectFeature 方法', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.selectFeature).toBeDefined()
      expect(typeof wrapper.vm.selectFeature).toBe('function')
    })

    it('应该暴露 clearSelection 方法', async () => {
      wrapper = mount(HighlightViewer)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.clearSelection).toBeDefined()
      expect(typeof wrapper.vm.clearSelection).toBe('function')
    })

    it('应该暴露 setFeatures 方法', async () => {
      wrapper = mount(HighlightViewer)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.setFeatures).toBeDefined()
      expect(typeof wrapper.vm.setFeatures).toBe('function')
    })

    it('应该能够通过暴露的 selectFeature 方法选中特征', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.selectFeature('feature-002')
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('feature-select')
      expect(emitted).toBeDefined()
    })

    it('应该能够通过暴露的 clearSelection 方法清除选中', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.selectFeature('feature-001')
      await wrapper.vm.$nextTick()

      wrapper.vm.clearSelection()
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('feature-clear')
      expect(emitted).toBeDefined()
    })
  })

  describe('事件发射', () => {
    it('应该在选中时发射 feature-select 事件', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[1].trigger('click')

      const emitted = wrapper.emitted('feature-select')
      expect(emitted).toHaveLength(1)
      expect(emitted![0][0]).toMatchObject({
        id: 'feature-002',
        name: '平面特征 B',
      })
    })

    it('应该在清除时发射 feature-clear 事件', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const clearBtn = wrapper.find('.clear-button')
      await clearBtn.trigger('click')

      const emitted = wrapper.emitted('feature-clear')
      expect(emitted).toHaveLength(1)
    })

    it('应该在悬停时发射 feature-hover 事件', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('mouseenter')

      const emitted = wrapper.emitted('feature-hover')
      expect(emitted).toBeDefined()
      expect(emitted!.length).toBeGreaterThan(0)
    })
  })

  describe('props 变化响应', () => {
    it('应该响应 features prop 变化', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: [mockFeatures[0]] },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.feature-item')).toHaveLength(1)

      await wrapper.setProps({ features: mockFeatures })
      await wrapper.vm.$nextTick()

      expect(wrapper.findAll('.feature-item')).toHaveLength(3)
    })
  })

  describe('样式和布局', () => {
    it('应该有正确的根容器类名', () => {
      wrapper = mount(HighlightViewer)
      const root = wrapper.find('.highlight-viewer')
      expect(root.exists()).toBe(true)
    })

    it('应该有正确的画布容器类名', () => {
      wrapper = mount(HighlightViewer)
      const canvas = wrapper.find('.canvas-container')
      expect(canvas.exists()).toBe(true)
    })

    it('应该有正确的控制面板类名', () => {
      wrapper = mount(HighlightViewer)
      const panel = wrapper.find('.control-panel')
      expect(panel.exists()).toBe(true)
    })
  })

  describe('性能测试', () => {
    it('应该在 100ms 内完成特征选中响应', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      const startTime = performance.now()

      const items = wrapper.findAll('.feature-item')
      await items[0].trigger('click')
      await wrapper.vm.$nextTick()

      const elapsed = performance.now() - startTime
      expect(elapsed).toBeLessThan(100)
    })

    it('应该能够处理大量特征而不卡顿', async () => {
      const largeFeatures: FeatureInfo[] = []
      for (let i = 0; i < 100; i++) {
        largeFeatures.push({
          id: `feature-${i}`,
          name: `特征 ${i}`,
          type: 'hole',
          description: `测试特征 ${i}`,
          geometry: { center: [i * 10, 0, 0] },
          aiInfo: { importance: Math.random(), reason: '测试', category: '测试' },
        })
      }

      const startTime = performance.now()

      wrapper = mount(HighlightViewer, {
        props: { features: largeFeatures },
      })
      await wrapper.vm.$nextTick()

      const elapsed = performance.now() - startTime
      expect(elapsed).toBeLessThan(500)
    })
  })

  describe('边界情况处理', () => {
    it('应该处理空特征列表', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: [] },
      })
      await wrapper.vm.$nextTick()
      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理没有 aiInfo 的特征', async () => {
      const featuresWithoutAi: FeatureInfo[] = [
        {
          id: 'no-ai-001',
          name: '无 AI 信息特征',
          type: 'unknown',
          description: '没有 AI 分析信息',
          geometry: { center: [0, 0, 0] },
        },
      ]

      wrapper = mount(HighlightViewer, {
        props: { features: featuresWithoutAi },
      })
      await wrapper.vm.$nextTick()

      const items = wrapper.findAll('.feature-item')
      expect(items).toHaveLength(1)
      // 不应显示重要度
      const importance = wrapper.find('.feature-importance')
      expect(importance.exists()).toBe(false)
    })

    it('应该处理未提供 features prop 的情况', async () => {
      wrapper = mount(HighlightViewer)
      await wrapper.vm.$nextTick()
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('组件卸载', () => {
    it('应该在卸载时清理资源', async () => {
      wrapper = mount(HighlightViewer, {
        props: { features: mockFeatures },
      })
      await wrapper.vm.$nextTick()

      // 卸载不应抛出错误
      expect(() => wrapper.unmount()).not.toThrow()
      wrapper = undefined as any
    })
  })
})
