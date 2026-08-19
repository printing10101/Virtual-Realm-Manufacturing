/**
 * 方言管理前端插件测试（前端插件管道闭环）
 *
 * 验证：
 * - 插件注册后贡献出现在 workspace.panel 扩展点
 * - 组件加载器能解析 src/plugins/dialect-manager/DialectManagerPanel.vue
 * - 幂等注册（重复调用不产生重复面板）
 * - 卸载后贡献移除
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { extensionRegistry } from '@/composables/useExtensionRegistry'

import {
  registerDialectManagerPlugin,
  unregisterDialectManagerPlugin,
  DIALECT_MANAGER_PLUGIN_ID,
} from '@/plugins/dialect-manager'

describe('dialect-manager 前端插件', () => {
  beforeEach(() => {
    extensionRegistry.clear()
  })

  it('注册后贡献出现在 workspace.panel 扩展点', () => {
    registerDialectManagerPlugin()

    const panels = extensionRegistry.list('workspace.panel')
    expect(panels).toHaveLength(1)
    expect(panels[0].plugin_id).toBe(DIALECT_MANAGER_PLUGIN_ID)
    expect(panels[0].component_url).toBe('dialect-manager/DialectManagerPanel.vue')
    // 元信息供 WorkspacePanelHost 渲染标题
    expect(panels[0].metadata?.title).toBe('后处理器方言')
  })

  it('重复注册幂等（不产生重复面板）', () => {
    registerDialectManagerPlugin()
    registerDialectManagerPlugin()
    registerDialectManagerPlugin()

    const panels = extensionRegistry.list('workspace.panel')
    expect(panels).toHaveLength(1)
  })

  it('组件加载器解析到真实面板组件', async () => {
    registerDialectManagerPlugin()
    const panels = extensionRegistry.list('workspace.panel')
    expect(panels).toHaveLength(1)

    const comp = await extensionRegistry.loadComponent(panels[0])
    // 组件定义对象（Vue SFC 编译产物）存在且为对象
    expect(comp).toBeTruthy()
    expect(typeof comp).toBe('object')
  })

  it('卸载后贡献移除', () => {
    registerDialectManagerPlugin()
    expect(extensionRegistry.list('workspace.panel')).toHaveLength(1)

    unregisterDialectManagerPlugin()
    expect(extensionRegistry.list('workspace.panel')).toHaveLength(0)
  })
})
