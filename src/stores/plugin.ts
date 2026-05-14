import { defineStore } from 'pinia'
import axios from 'axios'

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
  config_schema: Record<string, any>
  min_core_version: string
  max_core_version: string
  plugin_path: string
  status: string
  config: Record<string, any>
  enabled_at?: number
  disabled_at?: number
  installed_at?: number
}

export interface PluginDetail {
  metadata: Plugin
  has_instance: boolean
  context_keys: string[]
  dependency_tree: any
  capabilities: string[]
  worker?: any
}

export interface PluginState {
  plugins: Plugin[]
  currentPlugin: PluginDetail | null
  loading: boolean
  error: string | null
}

export const usePluginStore = defineStore('plugin', {
  state: (): PluginState => ({
    plugins: [],
    currentPlugin: null,
    loading: false,
    error: null,
  }),

  getters: {
    enabledPlugins: (state) => state.plugins.filter((p) => p.status === 'enabled'),
    disabledPlugins: (state) => state.plugins.filter((p) => p.status === 'disabled'),
    adapterPlugins: (state) => state.plugins.filter((p) => p.plugin_type === 'adapter'),
    dataSourcePlugins: (state) => state.plugins.filter((p) => p.plugin_type === 'data_source'),
    analyzerPlugins: (state) => state.plugins.filter((p) => p.plugin_type === 'analyzer'),
    visualizationPlugins: (state) => state.plugins.filter((p) => p.plugin_type === 'visualization'),
  },

  actions: {
    async fetchPlugins() {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get('/api/v1/plugins')
        this.plugins = response.data.data.plugins
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async fetchPluginDetail(pluginId: string) {
      this.loading = true
      this.error = null
      try {
        const response = await axios.get(`/api/v1/plugins/${pluginId}`)
        this.currentPlugin = response.data.data
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async enablePlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/enable`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async disablePlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/disable`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async uninstallPlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.delete(`/api/v1/plugins/${pluginId}`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async updatePluginConfig(pluginId: string, config: Record<string, any>) {
      this.loading = true
      try {
        await axios.put(`/api/v1/plugins/${pluginId}/config`, config)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },

    async reloadPlugin(pluginId: string) {
      this.loading = true
      try {
        await axios.post(`/api/v1/plugins/${pluginId}/reload`)
        await this.fetchPlugins()
      } catch (err: any) {
        this.error = err.message
      } finally {
        this.loading = false
      }
    },
  },
})
