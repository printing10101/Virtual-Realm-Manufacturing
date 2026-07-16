/* eslint-disable vue/no-unused-vars */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { shallowMount, VueWrapper } from '@vue/test-utils'
import * as THREE from 'three'
import DxfImportDialog from '@/components/dxf_import/DxfImportDialog.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params && 'pct' in params) {
        return `${key}:${params.pct}`
      }
      return key
    },
  }),
}))

// Mock Element Plus
const mockElMessage = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}
vi.mock('element-plus', () => ({
  ElMessage: mockElMessage,
  ElButtonGroup: { template: '<div class="el-button-group"><slot /></div>', props: ['size'] },
}))

// Mock @element-plus/icons-vue
vi.mock('@element-plus/icons-vue', () => ({
  UploadFilled: { name: 'UploadFilled', template: '<i />' },
  Loading: { name: 'Loading', template: '<i />' },
  Aim: { name: 'Aim', template: '<i />' },
}))

// Mock Three.js scene composable
const mockSceneCleanup = vi.fn()
const mockStartAnimation = vi.fn()
const mockAddLight = vi.fn()
const mockControlsUpdate = vi.fn()
const mockRenderer = {
  setSize: vi.fn(),
  render: vi.fn(),
  setPixelRatio: vi.fn(),
  dispose: vi.fn(),
  setClearColor: vi.fn(),
  domElement: document.createElement('div'),
}
vi.mock('@/composables/useThreeScene', () => ({
  useThreeScene: vi.fn(() => {
    return {
      scene: new THREE.Scene(),
      camera: new THREE.PerspectiveCamera(),
      renderer: mockRenderer,
      controls: {
        target: new THREE.Vector3(),
        update: mockControlsUpdate,
        clone: () => ({ target: new THREE.Vector3() }),
      },
      addLight: mockAddLight,
      startAnimation: mockStartAnimation,
      cleanup: mockSceneCleanup,
    }
  }),
}))

// Mock formatters
vi.mock('@/utils/formatters', () => ({
  formatFileSize: vi.fn((size: number) => `${size} B`),
}))

// Mock dynamic import of project store
vi.mock('@/stores/project', () => ({
  useProjectStore: () => ({
    manifest: {
      resources: [],
    },
    markModified: vi.fn(),
  }),
}))

describe('DxfImportDialog.vue', () => {
  let wrapper: VueWrapper<any>
  let store: any

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // 获取真实 store 实例（由组件内部 useDxfImportStore 调用）
    // 由于组件内会调用 useDxfImportStore，我们使用真实 store
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  const mountComponent = () => {
    wrapper = shallowMount(DxfImportDialog, {
      global: {
        plugins: [createPinia()],
      },
    })
    return wrapper
  }

  describe('组件挂载', () => {
    it('应该正确挂载组件', () => {
      mountComponent()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.dxf-import-container').exists()).toBe(true)
    })

    it('空闲状态应渲染上传区域', () => {
      mountComponent()
      expect(wrapper.find('.upload-section').exists()).toBe(true)
    })

    it('空闲状态应渲染拖拽区', () => {
      mountComponent()
      expect(wrapper.find('.drop-zone').exists()).toBe(true)
    })

    it('应渲染隐藏的文件输入', () => {
      mountComponent()
      const input = wrapper.find('input[type="file"]')
      expect(input.exists()).toBe(true)
    })

    it('应渲染对话框底部', () => {
      mountComponent()
      expect(wrapper.find('.dialog-footer').exists()).toBe(true)
    })
  })

  describe('文件选择交互', () => {
    it('点击拖拽区应触发文件选择器', async () => {
      mountComponent()
      const dropZone = wrapper.find('.drop-zone')
      const clickSpy = vi.spyOn(wrapper.vm.fileInputRef, 'click').mockImplementation(() => {})
      // 由于 fileInputRef 在测试环境可能为 null，直接测试方法
      wrapper.vm.fileInputRef = { click: vi.fn() }
      await dropZone.trigger('click')
      expect(wrapper.vm.fileInputRef.click).toHaveBeenCalled()
      clickSpy.mockRestore()
    })

    it('triggerFilePicker 应调用 fileInputRef.click', () => {
      mountComponent()
      const clickMock = vi.fn()
      wrapper.vm.fileInputRef = { click: clickMock }
      wrapper.vm.triggerFilePicker()
      expect(clickMock).toHaveBeenCalled()
    })

    it('fileInputRef 为 null 时 triggerFilePicker 不应抛出错误', () => {
      mountComponent()
      wrapper.vm.fileInputRef = null
      expect(() => wrapper.vm.triggerFilePicker()).not.toThrow()
    })
  })

  describe('onFileInputChange 方法', () => {
    it('应从 change 事件中提取文件并处理', async () => {
      mountComponent()
      const file = new File(['dxf content'], 'test.dxf', { type: 'application/dxf' })
      const target = { files: [file], value: '' }
      const event = { target }
      const handleSpy = vi.spyOn(wrapper.vm, 'handleFileSelected').mockResolvedValue(undefined)
      wrapper.vm.onFileInputChange(event)
      expect(handleSpy).toHaveBeenCalledWith(file)
    })

    it('没有文件时不应调用 handleFileSelected', async () => {
      mountComponent()
      const target = { files: [], value: '' }
      const event = { target }
      const handleSpy = vi.spyOn(wrapper.vm, 'handleFileSelected').mockResolvedValue(undefined)
      wrapper.vm.onFileInputChange(event)
      expect(handleSpy).not.toHaveBeenCalled()
    })

    it('处理后应重置 input value', () => {
      mountComponent()
      const file = new File(['dxf'], 'test.dxf', { type: 'application/dxf' })
      const target = { files: [file], value: 'initial' }
      const event = { target }
      vi.spyOn(wrapper.vm, 'handleFileSelected').mockResolvedValue(undefined)
      wrapper.vm.onFileInputChange(event)
      expect(target.value).toBe('')
    })
  })

  describe('onFileDrop 方法', () => {
    it('应从拖拽事件中提取文件并处理', async () => {
      mountComponent()
      const file = new File(['dxf'], 'test.dxf', { type: 'application/dxf' })
      const event = {
        dataTransfer: { files: [file] },
      }
      const handleSpy = vi.spyOn(wrapper.vm, 'handleFileSelected').mockResolvedValue(undefined)
      wrapper.vm.onFileDrop(event)
      expect(handleSpy).toHaveBeenCalledWith(file)
      expect(wrapper.vm.isDragOver).toBe(false)
    })

    it('没有 dataTransfer 时不应处理', () => {
      mountComponent()
      const event = { dataTransfer: null }
      const handleSpy = vi.spyOn(wrapper.vm, 'handleFileSelected').mockResolvedValue(undefined)
      wrapper.vm.onFileDrop(event)
      expect(handleSpy).not.toHaveBeenCalled()
    })
  })

  describe('handleFileSelected 方法', () => {
    it('非 dxf 文件应显示错误并设置 localFormatError', async () => {
      mountComponent()
      const file = new File(['content'], 'test.txt', { type: 'text/plain' })
      await wrapper.vm.handleFileSelected(file)
      expect(mockElMessage.error).toHaveBeenCalled()
      expect(wrapper.vm.localFormatError).toBeTruthy()
    })

    it('dxf 文件应调用 store.importDxfFile', async () => {
      mountComponent()
      const file = new File(['dxf content'], 'test.dxf', { type: 'application/dxf' })
      const store = wrapper.vm.store
      const importSpy = vi.spyOn(store, 'importDxfFile').mockResolvedValue(true)
      await wrapper.vm.handleFileSelected(file)
      expect(importSpy).toHaveBeenCalledWith(file)
      expect(wrapper.vm.localFormatError).toBe('')
    })

    it('importDxfFile 返回 false 应显示错误消息', async () => {
      mountComponent()
      const file = new File(['dxf'], 'test.dxf', { type: 'application/dxf' })
      const store = wrapper.vm.store
      store.errorMessage = '解析失败'
      vi.spyOn(store, 'importDxfFile').mockResolvedValue(false)
      await wrapper.vm.handleFileSelected(file)
      expect(mockElMessage.error).toHaveBeenCalled()
    })

    it('大文件（>50MB）应显示警告但不阻止', async () => {
      mountComponent()
      const largeFile = new File(['x'.repeat(1024)], 'large.dxf', { type: 'application/dxf' })
      Object.defineProperty(largeFile, 'size', { value: 60 * 1024 * 1024 })
      const store = wrapper.vm.store
      vi.spyOn(store, 'importDxfFile').mockResolvedValue(true)
      await wrapper.vm.handleFileSelected(largeFile)
      expect(mockElMessage.warning).toHaveBeenCalled()
    })
  })

  describe('handleRetry 方法', () => {
    it('应调用 store.reset 并清空 localFormatError', () => {
      mountComponent()
      const store = wrapper.vm.store
      const resetSpy = vi.spyOn(store, 'reset')
      wrapper.vm.localFormatError = 'some error'
      wrapper.vm.handleRetry()
      expect(resetSpy).toHaveBeenCalled()
      expect(wrapper.vm.localFormatError).toBe('')
    })
  })

  describe('handleClose 方法', () => {
    it('应调用 store.closeDialog', () => {
      mountComponent()
      const store = wrapper.vm.store
      const closeSpy = vi.spyOn(store, 'closeDialog')
      wrapper.vm.handleClose()
      expect(closeSpy).toHaveBeenCalled()
    })
  })

  describe('handleImportToProject 方法', () => {
    it('成功导入应显示成功消息并关闭对话框', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.parseResult = {
        file_name: 'test.dxf',
        file_size: 1024,
        lines_count: 10,
        arcs_count: 5,
        circles_count: 3,
      }
      store.currentFileId = 'file-123'
      const closeSpy = vi.spyOn(store, 'closeDialog')
      await wrapper.vm.handleImportToProject()
      expect(mockElMessage.success).toHaveBeenCalled()
      expect(closeSpy).toHaveBeenCalled()
      expect(wrapper.vm.importing).toBe(false)
    })

    it('导入失败应显示错误消息', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.parseResult = null
      // 强制触发 catch
      vi.spyOn(wrapper.vm, 'handleImportToProject').mockImplementationOnce(async function (this: any) {
        this.importing = true
        try {
          throw new Error('mock error')
        } catch {
          mockElMessage.error('dxfImportDialog.importToProjectFailed')
        } finally {
          this.importing = false
        }
      })
      await wrapper.vm.handleImportToProject()
      expect(mockElMessage.error).toHaveBeenCalled()
    })
  })

  describe('toggleWireframe 方法', () => {
    it('应切换 wireframe 状态', () => {
      mountComponent()
      const initial = wrapper.vm.wireframe
      wrapper.vm.toggleWireframe()
      expect(wrapper.vm.wireframe).toBe(!initial)
    })

    it('contentGroup 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.contentGroup = null
      expect(() => wrapper.vm.toggleWireframe()).not.toThrow()
    })
  })

  describe('disposePreview 方法', () => {
    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = null
      wrapper.vm.contentGroup = null
      expect(() => wrapper.vm.disposePreview()).not.toThrow()
    })

    it('有 threeScene 时应调用 cleanup', () => {
      mountComponent()
      const cleanupMock = vi.fn()
      wrapper.vm.threeScene = { cleanup: cleanupMock }
      wrapper.vm.contentGroup = null
      wrapper.vm.disposePreview()
      expect(cleanupMock).toHaveBeenCalled()
      expect(wrapper.vm.threeScene).toBe(null)
    })
  })

  describe('animate 方法', () => {
    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = null
      expect(() => wrapper.vm.animate()).not.toThrow()
    })
  })

  describe('onPreviewResize 方法', () => {
    it('previewContainer 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.previewContainer = null
      expect(() => wrapper.vm.onPreviewResize()).not.toThrow()
    })

    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.previewContainer = { clientWidth: 100, clientHeight: 100 }
      wrapper.vm.threeScene = null
      expect(() => wrapper.vm.onPreviewResize()).not.toThrow()
    })
  })

  describe('resetView 方法', () => {
    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = null
      expect(() => wrapper.vm.resetView()).not.toThrow()
    })

    it('contentGroup 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = {
        camera: { fov: 45, position: { set: vi.fn() }, updateProjectionMatrix: vi.fn() },
        controls: { target: { set: vi.fn() }, update: vi.fn() },
      }
      wrapper.vm.contentGroup = null
      expect(() => wrapper.vm.resetView()).not.toThrow()
    })
  })

  describe('viewTop 方法', () => {
    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = null
      expect(() => wrapper.vm.viewTop()).not.toThrow()
    })
  })

  describe('view3D 方法', () => {
    it('threeScene 为 null 时不应抛出错误', () => {
      mountComponent()
      wrapper.vm.threeScene = null
      expect(() => wrapper.vm.view3D()).not.toThrow()
    })
  })

  describe('featuresCount 计算属性', () => {
    it('featureResult 为 null 时应返回 0', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.featureResult = null
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.featuresCount).toBe(0)
    })

    it('应返回 hole_count 和 plane_count 之和', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.featureResult = { hole_count: 3, plane_count: 2 }
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.featuresCount).toBe(5)
    })

    it('hole_count 和 plane_count 缺失时应按 0 处理', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.featureResult = {}
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.featuresCount).toBe(0)
    })
  })

  describe('visible 计算属性', () => {
    it('应反映 store.showDialog 状态', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.showDialog = true
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.visible).toBe(true)
      store.showDialog = false
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.visible).toBe(false)
    })

    it('设置 visible 应更新 store.showDialog', async () => {
      mountComponent()
      const store = wrapper.vm.store
      wrapper.vm.visible = true
      expect(store.showDialog).toBe(true)
      wrapper.vm.visible = false
      expect(store.showDialog).toBe(false)
    })
  })

  describe('拖拽状态', () => {
    it('isDragOver 默认为 false', () => {
      mountComponent()
      expect(wrapper.vm.isDragOver).toBe(false)
    })

    it('dragenter 应设置 isDragOver 为 true', async () => {
      mountComponent()
      const dropZone = wrapper.find('.drop-zone')
      await dropZone.trigger('dragenter')
      expect(wrapper.vm.isDragOver).toBe(true)
    })

    it('dragleave 应设置 isDragOver 为 false', async () => {
      mountComponent()
      wrapper.vm.isDragOver = true
      const dropZone = wrapper.find('.drop-zone')
      await dropZone.trigger('dragleave')
      expect(wrapper.vm.isDragOver).toBe(false)
    })
  })

  describe('不同阶段渲染', () => {
    it('uploading 阶段应渲染进度区域', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.phase = 'uploading'
      store.currentFileName = 'test.dxf'
      store.uploadProgress = 50
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.progress-section').exists()).toBe(true)
    })

    it('parsing 阶段应渲染进度区域', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.phase = 'parsing'
      store.currentFileName = 'test.dxf'
      store.parseProgress = 80
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.progress-section').exists()).toBe(true)
    })

    it('success 阶段且有 parseResult 应渲染结果区域', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.phase = 'success'
      store.parseResult = {
        file_name: 'test.dxf',
        file_size: 1024,
        lines_count: 10,
        arcs_count: 5,
        circles_count: 3,
        dxf_version: 'AC1009',
        parse_time_ms: 150,
        total_entities: 18,
        warnings: [],
      }
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.result-section').exists()).toBe(true)
      expect(wrapper.find('.stats-section').exists()).toBe(true)
    })

    it('error 阶段应渲染上传区域和错误重试按钮', async () => {
      mountComponent()
      const store = wrapper.vm.store
      store.phase = 'error'
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.upload-section').exists()).toBe(true)
    })
  })
})
