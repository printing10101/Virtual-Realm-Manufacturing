import { defineStore } from 'pinia'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

/**
 * 插件元数据接口
 * 描述插件的基本信息、配置和能力。
 */
export interface Plugin {
  id: string
  name: string
  version: string
  author: string
  description: string
  entry_point: string
  plugin_type: string
  capabilities: string[]
  dependencies: Array<{ name: string; version: string; required: boolean }>
  config_schema: Record<string, unknown>
  min_core_version: string
  max_core_version: string
  plugin_path: string
  status: string
  config: Record<string, unknown>
  enabled_at?: number
  disabled_at?: number
  installed_at?: number
}

/**
 * Worker 进程信息接口
 */
export interface WorkerInfo {
  status: string
  pid: number
  port: number
  uptime: number
}

/**
 * 依赖节点接口
 */
export interface DependencyNode {
  id: string
  name: string
  version: string
  status?: string
  dependencies?: DependencyNode[]
}

/**
 * 插件详情接口
 * 包含插件元数据、实例状态和依赖树等信息。
 */
export interface PluginDetail {
  metadata: Plugin
  has_instance: boolean
  context_keys: string[]
  dependency_tree: DependencyNode | null
  capabilities: string[]
  worker?: WorkerInfo
}

/** 插件状态接口 */
export interface PluginState {
  plugins: Plugin[]
  currentPlugin: PluginDetail | null
  loading: boolean
  error: string | null
}

/**
 * 插件管理 Store
 * 管理插件的加载、启用、禁用、卸载和配置更新。
 */
export const usePluginStore = defineStore('plugin', {
  state: (): PluginState => ({
    plugins: [],
    currentPlugin: null,
    loading: false,
    error: null,
  }),

  getters: {
    /** 已启用的插件列表 */
    enabledPlugins: (state): Plugin[] => state.plugins.filter((p) => p.status === 'enabled'),
    /** 已禁用的插件列表 */
    disabledPlugins: (state): Plugin[] => state.plugins.filter((p) => p.status === 'disabled'),
    /** 适配器类型插件 */
    adapterPlugins: (state): Plugin[] => state.plugins.filter((p) => p.plugin_type === 'adapter'),
    /** 数据源类型插件 */
    dataSourcePlugins: (state): Plugin[] => state.plugins.filter((p) => p.plugin_type === 'data_source'),
    /** 分析器类型插件 */
    analyzerPlugins: (state): Plugin[] => state.plugins.filter((p) => p.plugin_type === 'analyzer'),
    /** 可视化类型插件 */
    visualizationPlugins: (state): Plugin[] => state.plugins.filter((p) => p.plugin_type === 'visualization'),
  },

  actions: {
    /**
     * 获取插件列表
     * @returns void
     */
    async fetchPlugins(): Promise<void> {
      this.loading = true
      this.error = null
      try {
        const response = await http.get(API_CONFIG.PLUGINS)
        this.plugins = response.data.data.plugins
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 获取插件详情
     * @param pluginId - 插件ID
     * @returns void
     */
    async fetchPluginDetail(pluginId: string): Promise<void> {
      this.loading = true
      this.error = null
      try {
        const response = await http.get(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}`))
        this.currentPlugin = response.data.data
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 启用插件
     * @param pluginId - 插件ID
     * @returns void
     */
    async enablePlugin(pluginId: string): Promise<void> {
      this.loading = true
      try {
        await http.post(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}/enable`))
        await this.fetchPlugins()
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 禁用插件
     * @param pluginId - 插件ID
     * @returns void
     */
    async disablePlugin(pluginId: string): Promise<void> {
      this.loading = true
      try {
        await http.post(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}/disable`))
        await this.fetchPlugins()
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 卸载插件
     * @param pluginId - 插件ID
     * @returns void
     */
    async uninstallPlugin(pluginId: string): Promise<void> {
      this.loading = true
      try {
        await http.delete(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}`))
        await this.fetchPlugins()
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 更新插件配置
     * @param pluginId - 插件ID
     * @param config - 配置数据
     * @returns void
     */
    async updatePluginConfig(pluginId: string, config: Record<string, unknown>): Promise<void> {
      this.loading = true
      try {
        await http.put(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}/config`), config)
        await this.fetchPlugins()
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },

    /**
     * 重新加载插件
     * @param pluginId - 插件ID
     * @returns void
     */
    async reloadPlugin(pluginId: string): Promise<void> {
      this.loading = true
      try {
        await http.post(buildApiPath(API_CONFIG.PLUGINS, `/${pluginId}/reload`))
        await this.fetchPlugins()
      } catch (err: unknown) {
        this.error = (err as Error).message
      } finally {
        this.loading = false
      }
    },
  },
})
