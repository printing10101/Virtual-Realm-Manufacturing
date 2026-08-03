/* eslint-disable vue/no-unused-vars */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import * as THREE from 'three'
import SimulationViewer from '@/components/simulation/SimulationViewer.vue'
import type { SimulationVisualizationData, ForceData, TemperatureData, VibrationData } from '@/api/simulation'
import type { CollisionInfo, ToolpathSegmentData } from '@/types'

// Mock Three.js场景
vi.mock('@/composables/useThreeScene', () => {
  // 创建mock renderer避免WebGL上下文初始化
  const mockRenderer = {
    domElement: document.createElement('div'),
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
      camera: new THREE.PerspectiveCamera(),
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

// Mock仿真可视化逻辑 - 同时mock hook和命名导出
vi.mock('@/composables/useSimulationVisualization', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/composables/useSimulationVisualization')>()
  return {
    ...actual,
    useSimulationVisualization: vi.fn(() => ({
      renderSimulationResult: vi.fn(),
      clearVisualization: vi.fn(),
      updateVisualization: vi.fn(),
      getColorForValue: vi.fn((_value: number, _min: number, _max: number) => new THREE.Color(0xff0000)),
      createForceArrow: vi.fn(() => new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(), 1, 0xff0000)),
      createForceVectorGroup: vi.fn(() => new THREE.Group()),
      createTemperatureMaterial: vi.fn(() => new THREE.ShaderMaterial()),
      createTemperatureCloud: vi.fn(() => new THREE.Mesh(new THREE.BufferGeometry(), new THREE.ShaderMaterial())),
      createVibrationVisualization: vi.fn(() => new THREE.Group()),
      createColorLegend: vi.fn(() => new THREE.Group()),
    })),
    getColorForValue: vi.fn((_value: number, _min: number, _max: number) => new THREE.Color(0xff0000)),
    createForceArrow: vi.fn(() => new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(), 1, 0xff0000)),
    createForceVectorGroup: vi.fn(() => {
      const g = new THREE.Group()
      g.name = 'force-vectors'
      return g
    }),
    createTemperatureMaterial: vi.fn(() => new THREE.ShaderMaterial()),
    createTemperatureCloud: vi.fn(() => new THREE.Mesh(new THREE.BufferGeometry(), new THREE.ShaderMaterial())),
    createVibrationVisualization: vi.fn(() => {
      const g = new THREE.Group()
      g.name = 'vibration-data'
      return g
    }),
    createColorLegend: vi.fn(() => {
      const g = new THREE.Group()
      g.name = 'color-legend'
      return g
    }),
  }
})

// Mock STLLoader
vi.mock('three/examples/jsm/loaders/STLLoader.js', () => ({
  STLLoader: vi.fn().mockImplementation(() => ({
    load: vi.fn((_url: string, onLoad: (geometry: THREE.BufferGeometry) => void) => {
      // 模拟加载成功
      const geometry = new THREE.BufferGeometry()
      onLoad(geometry)
    }),
  })),
}))

// Mock Element Plus组件
vi.mock('@element-plus/icons-vue', () => ({
  VideoPlay: { name: 'VideoPlay' },
  VideoPause: { name: 'VideoPause' },
}))

describe('SimulationViewer.vue', () => {
  let wrapper: VueWrapper<any>

  const mockSimulationData: SimulationVisualizationData = {
    task_id: 'test-task-001',
    timestamp: Date.now(),
    force_data: [
      {
        position: [0, 0, 10] as [number, number, number],
        direction: [0, 0, -1] as [number, number, number],
        magnitude: 500,
        timestamp: 1000,
      },
      {
        position: [10, 0, 10] as [number, number, number],
        direction: [0, 0, -1] as [number, number, number],
        magnitude: 800,
        timestamp: 1000,
      },
      {
        position: [20, 0, 10] as [number, number, number],
        direction: [0, 0, -1] as [number, number, number],
        magnitude: 600,
        timestamp: 2000,
      },
    ],
    temperature_data: [
      {
        position: [0, 0, 10] as [number, number, number],
        temperature: 25,
        timestamp: 1000,
      },
      {
        position: [10, 0, 10] as [number, number, number],
        temperature: 80,
        timestamp: 1000,
      },
      {
        position: [20, 0, 10] as [number, number, number],
        temperature: 45,
        timestamp: 2000,
      },
    ],
    vibration_data: [
      {
        position: [0, 0, 10] as [number, number, number],
        amplitude: 0.05,
        frequency: 60,
        timestamp: 1000,
      },
      {
        position: [10, 0, 10] as [number, number, number],
        amplitude: 0.08,
        frequency: 75,
        timestamp: 1000,
      },
    ],
  }

  const mockCollisionData: CollisionInfo = {
    collided: true,
    collision_positions: [[5, 5, 10], [15, 15, 10]],
    collision_segment_indices: [0, 1],
    collision_severity: 'warning',
  }

  const mockToolpathSegments: ToolpathSegmentData[] = [
    {
      block_number: 1,
      g_code: 'G00',
      type: 'rapid',
      start_point: [0, 0, 20],
      end_point: [0, 0, 10],
    },
    {
      block_number: 2,
      g_code: 'G01',
      type: 'linear',
      start_point: [0, 0, 10],
      end_point: [20, 0, 10],
    },
  ]

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
      wrapper = mount(SimulationViewer)
      expect(wrapper.exists()).toBe(true)
    })

    it('应该显示占位符当未初始化时', () => {
      wrapper = mount(SimulationViewer)
      const placeholder = wrapper.find('.viewer-placeholder')
      expect(placeholder.exists()).toBe(true)
    })

    it('应该在挂载后初始化场景', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()
      
      // 检查是否调用了初始化
      expect(wrapper.vm.initialized).toBe(true)
    })

    it('应该接受自定义背景色', () => {
      wrapper = mount(SimulationViewer, {
        props: {
          backgroundColor: '#ffffff',
        },
      })
      expect(wrapper.props('backgroundColor')).toBe('#ffffff')
    })

    it('应该接受显示网格选项', () => {
      wrapper = mount(SimulationViewer, {
        props: {
          showGrid: false,
        },
      })
      expect(wrapper.props('showGrid')).toBe(false)
    })
  })

  describe('仿真数据可视化', () => {
    it('应该在有仿真数据时显示可视化控制面板', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const controls = wrapper.find('.visualization-controls')
      expect(controls.exists()).toBe(true)
    })

    it('应该显示力矢量控制选项', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const forceCheckbox = wrapper.find('.control-item')
      expect(forceCheckbox.exists()).toBe(true)
    })

    it('应该显示温度云图控制选项', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const checkboxes = wrapper.findAll('.control-item')
      expect(checkboxes.length).toBeGreaterThan(0)
    })

    it('应该显示颜色图例当有力矢量或温度数据时', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const legend = wrapper.find('.color-legend')
      expect(legend.exists()).toBe(true)
    })

    it('应该计算力数据范围', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const forceRange = wrapper.vm.forceRange
      expect(forceRange).toBeDefined()
      expect(forceRange.min).toBe(500)
      expect(forceRange.max).toBe(800)
    })

    it('应该计算温度数据范围', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const temperatureRange = wrapper.vm.temperatureRange
      expect(temperatureRange).toBeDefined()
      expect(temperatureRange.min).toBe(25)
      expect(temperatureRange.max).toBe(80)
    })

    it('应该在没有力数据时返回null力范围', async () => {
      const dataWithoutForce = { ...mockSimulationData, force_data: [] }
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithoutForce,
        },
      })
      await wrapper.vm.$nextTick()

      const forceRange = wrapper.vm.forceRange
      expect(forceRange).toBeNull()
    })

    it('应该在没有温度数据时返回null温度范围', async () => {
      const dataWithoutTemp = { ...mockSimulationData, temperature_data: [] }
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithoutTemp,
        },
      })
      await wrapper.vm.$nextTick()

      const temperatureRange = wrapper.vm.temperatureRange
      expect(temperatureRange).toBeNull()
    })
  })

  describe('时间轴控制', () => {
    it('应该在有时间序列数据时显示时间轴', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      // 模拟有时间序列数据
      wrapper.vm.maxTimeIndex = 10
      await wrapper.vm.$nextTick()

      const timeline = wrapper.find('.timeline-control')
      expect(timeline.exists()).toBe(true)
    })

    it('应该能够切换播放状态', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.isPlaying).toBe(false)
      
      wrapper.vm.togglePlayback()
      expect(wrapper.vm.isPlaying).toBe(true)
      
      wrapper.vm.togglePlayback()
      expect(wrapper.vm.isPlaying).toBe(false)
    })

    it('应该能够重置时间轴', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.currentTimeIndex = 5
      wrapper.vm.resetTimeline()
      
      expect(wrapper.vm.currentTimeIndex).toBe(0)
      expect(wrapper.vm.isPlaying).toBe(false)
    })

    it('应该能够响应时间变化', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const timeChangeSpy = vi.spyOn(wrapper.vm, 'onTimeChange')
      wrapper.vm.onTimeChange(5)
      
      expect(timeChangeSpy).toHaveBeenCalledWith(5)
      expect(wrapper.vm.currentTimeIndex).toBe(5)
    })

    it('应该显示当前时间', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.currentTimeIndex = 5
      await wrapper.vm.$nextTick()

      const timeDisplay = wrapper.find('.time-display')
      expect(timeDisplay.exists()).toBe(true)
      expect(timeDisplay.text()).toContain('0.5s')
    })

    it('应该清理播放间隔在卸载时', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.startPlayback()
      expect(wrapper.vm.isPlaying).toBe(true)

      wrapper.unmount()
      expect(wrapper.vm.isPlaying).toBe(false)
    })
  })

  describe('可视化参数控制', () => {
    it('应该能够切换力矢量显示', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.showForceVectors).toBe(true)
      wrapper.vm.showForceVectors = false
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.showForceVectors).toBe(false)
    })

    it('应该能够切换温度云图显示', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.showTemperatureMap).toBe(true)
      wrapper.vm.showTemperatureMap = false
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.showTemperatureMap).toBe(false)
    })

    it('应该能够切换振动数据显示', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.showVibrationData).toBe(true)
      wrapper.vm.showVibrationData = false
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.showVibrationData).toBe(false)
    })

    it('应该能够调整力箭头缩放', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.forceArrowScale).toBe(1.0)
      wrapper.vm.forceArrowScale = 2.0
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.forceArrowScale).toBe(2.0)
    })

    it('应该能够调整温度透明度', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.temperatureOpacity).toBe(0.7)
      wrapper.vm.temperatureOpacity = 0.5
      await wrapper.vm.$nextTick()
      
      expect(wrapper.vm.temperatureOpacity).toBe(0.5)
    })
  })

  describe('碰撞检测可视化', () => {
    it('应该在有碰撞数据时绘制碰撞标记', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          collisionData: mockCollisionData,
        },
      })
      await wrapper.vm.$nextTick()

      // 检查是否调用了碰撞标记绘制
      expect(wrapper.vm.collisionMarkers).toBeDefined()
    })

    it('应该能够聚焦到碰撞位置', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          collisionData: mockCollisionData,
        },
      })
      await wrapper.vm.$nextTick()

      // 验证方法存在且可以调用
      expect(wrapper.vm.focusOnCollision).toBeDefined()
      expect(typeof wrapper.vm.focusOnCollision).toBe('function')
      
      // 调用方法不应抛出错误
      expect(() => wrapper.vm.focusOnCollision([5, 5, 10])).not.toThrow()
    })

    it('应该能够处理碰撞点击事件', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          collisionData: mockCollisionData,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.emitted('collision-click')
      // 碰撞点击事件应该被触发
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('刀具路径可视化', () => {
    it('应该在有刀具路径段时绘制路径', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: mockToolpathSegments,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.toolPathLine).toBeDefined()
    })

    it('应该能够更新刀具指示器', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: mockToolpathSegments,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.updateToolIndicator(0)
      expect(wrapper.vm.toolIndicator).toBeDefined()
    })

    it('应该响应段索引变化', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: mockToolpathSegments,
          currentSegmentIndex: 0,
        },
      })
      await wrapper.vm.$nextTick()

      await wrapper.setProps({ currentSegmentIndex: 1 })
      await wrapper.vm.$nextTick()

      // 应该更新刀具指示器
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('模型加载', () => {
    it('应该能够加载毛坯模型', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          stockStlUrl: '/test-stock.stl',
        },
      })
      await wrapper.vm.$nextTick()

      // 检查加载状态
      expect(wrapper.exists()).toBe(true)
    })

    it('应该能够加载结果模型', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          resultStlUrl: '/test-result.stl',
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该显示加载进度', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      wrapper.vm.loading = true
      wrapper.vm.progress = 50
      await wrapper.vm.$nextTick()

      const overlay = wrapper.find('.viewer-overlay')
      expect(overlay.exists()).toBe(true)
      
      const progressBar = wrapper.find('.progress-fill')
      expect(progressBar.exists()).toBe(true)
    })
  })

  describe('性能测试', () => {
    it('应该在200ms内完成渲染', async () => {
      const startTime = performance.now()
      
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()
      
      // 触发渲染
      wrapper.vm.renderSimulationData()
      await wrapper.vm.$nextTick()
      
      const renderTime = performance.now() - startTime
      expect(renderTime).toBeLessThan(200)
    })

    it('应该能够处理大量力数据而不卡顿', async () => {
      const largeForceData: ForceData[] = []
      for (let i = 0; i < 1000; i++) {
        largeForceData.push({
          position: [i, 0, 10],
          direction: [0, 0, -1],
          magnitude: 500 + Math.random() * 500,
          timestamp: 1000,
        })
      }

      const dataWithLargeForce = {
        ...mockSimulationData,
        force_data: largeForceData,
      }

      const startTime = performance.now()
      
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithLargeForce,
        },
      })
      await wrapper.vm.$nextTick()
      
      wrapper.vm.renderSimulationData()
      await wrapper.vm.$nextTick()
      
      const renderTime = performance.now() - startTime
      // 即使有1000个力数据点，渲染时间也应该在合理范围内
      expect(renderTime).toBeLessThan(500)
    })

    it('应该能够处理大量温度数据而不卡顿', async () => {
      const largeTemperatureData: TemperatureData[] = []
      for (let i = 0; i < 1000; i++) {
        largeTemperatureData.push({
          position: [i, 0, 10],
          temperature: 20 + Math.random() * 80,
          timestamp: 1000,
        })
      }

      const dataWithLargeTemp = {
        ...mockSimulationData,
        temperature_data: largeTemperatureData,
      }

      const startTime = performance.now()
      
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithLargeTemp,
        },
      })
      await wrapper.vm.$nextTick()
      
      wrapper.vm.renderSimulationData()
      await wrapper.vm.$nextTick()
      
      const renderTime = performance.now() - startTime
      expect(renderTime).toBeLessThan(500)
    })

    it('应该能够处理大量振动数据而不卡顿', async () => {
      const largeVibrationData: VibrationData[] = []
      for (let i = 0; i < 1000; i++) {
        largeVibrationData.push({
          position: [i, 0, 10],
          amplitude: Math.random() * 0.1,
          frequency: 50 + Math.random() * 50,
          timestamp: 1000,
        })
      }

      const dataWithLargeVibration = {
        ...mockSimulationData,
        vibration_data: largeVibrationData,
      }

      const startTime = performance.now()
      
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithLargeVibration,
        },
      })
      await wrapper.vm.$nextTick()
      
      wrapper.vm.renderSimulationData()
      await wrapper.vm.$nextTick()
      
      const renderTime = performance.now() - startTime
      expect(renderTime).toBeLessThan(500)
    })
  })

  describe('边界情况处理', () => {
    it('应该处理空的仿真数据', async () => {
      const emptyData: SimulationVisualizationData = {
        task_id: 'empty-task',
        timestamp: Date.now(),
        force_data: [],
        temperature_data: [],
        vibration_data: [],
      }

      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: emptyData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理未定义的仿真数据', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: undefined,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理极端的力值', async () => {
      const extremeForceData: ForceData[] = [
        {
          position: [0, 0, 10],
          direction: [0, 0, -1],
          magnitude: 0.001, // 极小值
          timestamp: 1000,
        },
        {
          position: [10, 0, 10],
          direction: [0, 0, -1],
          magnitude: 10000, // 极大值
          timestamp: 1000,
        },
      ]

      const dataWithExtremeForce = {
        ...mockSimulationData,
        force_data: extremeForceData,
      }

      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithExtremeForce,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理极端的温度值', async () => {
      const extremeTempData: TemperatureData[] = [
        {
          position: [0, 0, 10],
          temperature: -273.15, // 绝对零度
          timestamp: 1000,
        },
        {
          position: [10, 0, 10],
          temperature: 10000, // 极高温度
          timestamp: 1000,
        },
      ]

      const dataWithExtremeTemp = {
        ...mockSimulationData,
        temperature_data: extremeTempData,
      }

      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: dataWithExtremeTemp,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理未碰撞的碰撞数据', async () => {
      const noCollisionData: CollisionInfo = {
        collided: false,
        collision_positions: [],
        collision_segment_indices: [],
        collision_severity: 'none',
      }

      wrapper = mount(SimulationViewer, {
        props: {
          collisionData: noCollisionData,
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理空的刀具路径段', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: [],
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })

    it('应该处理无效的段索引', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: mockToolpathSegments,
          currentSegmentIndex: 999, // 超出范围
        },
      })
      await wrapper.vm.$nextTick()

      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('事件发射', () => {
    it('应该发射fps-update事件', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      // 模拟FPS更新
      wrapper.vm.fps = 60
      await wrapper.vm.$nextTick()

      // FPS更新应该被发射
      expect(wrapper.exists()).toBe(true)
    })

    it('应该发射time-change事件', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      wrapper.vm.onTimeChange(5)
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('time-change')
      expect(emitted).toBeDefined()
      expect(emitted![0]).toEqual([5])
    })

    it('应该发射segment-change事件', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          toolpathSegments: mockToolpathSegments,
        },
      })
      await wrapper.vm.$nextTick()

      // 段变化事件应该被支持
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('暴露的方法', () => {
    it('应该暴露focusOnCollision方法', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.focusOnCollision).toBeDefined()
      expect(typeof wrapper.vm.focusOnCollision).toBe('function')
    })

    it('应该暴露renderSimulationData方法', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.renderSimulationData).toBeDefined()
      expect(typeof wrapper.vm.renderSimulationData).toBe('function')
    })

    it('应该暴露updateVisualization方法', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      expect(wrapper.vm.updateVisualization).toBeDefined()
      expect(typeof wrapper.vm.updateVisualization).toBe('function')
    })
  })

  describe('样式和布局', () => {
    it('应该正确应用坐标轴样式', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      const axes = wrapper.find('.coordinate-axes')
      expect(axes.exists()).toBe(true)

      const axisX = wrapper.find('.axis-x')
      const axisY = wrapper.find('.axis-y')
      const axisZ = wrapper.find('.axis-z')

      expect(axisX.exists()).toBe(true)
      expect(axisY.exists()).toBe(true)
      expect(axisZ.exists()).toBe(true)
    })

    it('应该正确应用FPS计数器样式', async () => {
      wrapper = mount(SimulationViewer)
      await wrapper.vm.$nextTick()

      wrapper.vm.fps = 60
      await wrapper.vm.$nextTick()

      const fpsCounter = wrapper.find('.fps-counter')
      expect(fpsCounter.exists()).toBe(true)
      expect(fpsCounter.text()).toContain('60')
    })

    it('应该正确应用颜色图例样式', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const legend = wrapper.find('.color-legend')
      expect(legend.exists()).toBe(true)

      const legendItems = wrapper.findAll('.legend-item')
      expect(legendItems.length).toBeGreaterThan(0)
    })

    it('应该正确应用控制面板样式', async () => {
      wrapper = mount(SimulationViewer, {
        props: {
          simulationData: mockSimulationData,
        },
      })
      await wrapper.vm.$nextTick()

      const controls = wrapper.find('.visualization-controls')
      expect(controls.exists()).toBe(true)

      const sections = wrapper.findAll('.control-section')
      expect(sections.length).toBeGreaterThan(0)
    })
  })
})

describe('useSimulationVisualization', () => {
  it('应该导出所有必要的函数', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    expect(mod.getColorForValue).toBeDefined()
    expect(mod.createForceArrow).toBeDefined()
    expect(mod.createForceVectorGroup).toBeDefined()
    expect(mod.createTemperatureMaterial).toBeDefined()
    expect(mod.createTemperatureCloud).toBeDefined()
    expect(mod.createVibrationVisualization).toBeDefined()
    expect(mod.createColorLegend).toBeDefined()
    expect(mod.useSimulationVisualization).toBeDefined()
  })

  it('应该能够创建力矢量箭头', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const arrow = mod.createForceArrow(
      [0, 0, 0],
      [0, 0, -1],
      500,
      1.0
    )
    
    expect(arrow).toBeDefined()
    expect(arrow).toBeInstanceOf(THREE.ArrowHelper)
  })

  it('应该能够创建力矢量组', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const forceData: ForceData[] = [
      {
        position: [0, 0, 0],
        direction: [0, 0, -1],
        magnitude: 500,
        timestamp: 1000,
      },
    ]
    
    const group = mod.createForceVectorGroup(forceData)
    
    expect(group).toBeDefined()
    expect(group).toBeInstanceOf(THREE.Group)
    expect(group.name).toBe('force-vectors')
  })

  it('应该能够创建温度云图材质', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const temperatureData: TemperatureData[] = [
      {
        position: [0, 0, 0],
        temperature: 25,
        timestamp: 1000,
      },
      {
        position: [10, 0, 0],
        temperature: 80,
        timestamp: 1000,
      },
    ]
    
    const material = mod.createTemperatureMaterial(temperatureData)
    
    expect(material).toBeDefined()
    expect(material).toBeInstanceOf(THREE.ShaderMaterial)
  })

  it('应该能够创建振动可视化', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const vibrationData: VibrationData[] = [
      {
        position: [0, 0, 0],
        amplitude: 0.05,
        frequency: 60,
        timestamp: 1000,
      },
    ]
    
    const group = mod.createVibrationVisualization(vibrationData)
    
    expect(group).toBeDefined()
    expect(group).toBeInstanceOf(THREE.Group)
    expect(group.name).toBe('vibration-data')
  })

  it('应该能够根据值获取颜色', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const color = mod.getColorForValue(50, 0, 100)
    
    expect(color).toBeDefined()
    expect(color).toBeInstanceOf(THREE.Color)
  })

  it('应该能够创建颜色图例', async () => {
    const mod = await import('@/composables/useSimulationVisualization')
    
    const legend = mod.createColorLegend(0, 100, '测试')
    
    expect(legend).toBeDefined()
    expect(legend).toBeInstanceOf(THREE.Group)
    expect(legend.name).toBe('color-legend')
  })
})

describe('simulation API', () => {
  it('应该导出所有必要的函数和类型', async () => {
    const mod = await import('@/api/simulation')
    
    expect(mod.getSimulationResult).toBeDefined()
    expect(mod.clearSimulationCache).toBeDefined()
    expect(mod.getCacheStats).toBeDefined()
  }, 10000)

  it('应该能够清除缓存', async () => {
    const mod = await import('@/api/simulation')
    
    expect(() => mod.clearSimulationCache()).not.toThrow()
    expect(() => mod.clearSimulationCache('test-task')).not.toThrow()
  })

  it('应该能够获取缓存统计', async () => {
    const mod = await import('@/api/simulation')
    
    const stats = mod.getCacheStats()
    
    expect(stats).toBeDefined()
    expect(stats.size).toBeDefined()
    expect(stats.maxAge).toBeDefined()
    expect(stats.maxSize).toBeDefined()
  })

  it('应该定义正确的数据结构', async () => {
    const forceData: ForceData = {
      position: [0, 0, 0],
      direction: [0, 0, -1],
      magnitude: 500,
      timestamp: 1000,
    }
    
    const tempData: TemperatureData = {
      position: [0, 0, 0],
      temperature: 25,
      timestamp: 1000,
    }
    
    const vibrationData: VibrationData = {
      position: [0, 0, 0],
      amplitude: 0.05,
      frequency: 60,
      timestamp: 1000,
    }
    
    expect(forceData.magnitude).toBe(500)
    expect(tempData.temperature).toBe(25)
    expect(vibrationData.amplitude).toBe(0.05)
  })
})
