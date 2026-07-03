#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n 国际化改造脚本
修改 RouterStatusPanel.vue 和 AutoDetectPanel.vue
"""

import re

def update_router_status_panel():
    """修改 RouterStatusPanel.vue"""
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\settings\RouterStatusPanel.vue'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加 useI18n 导入
    content = re.sub(
        r"(import \{ computed, ref, watch \} from 'vue')",
        r"\1\nimport { useI18n } from 'vue-i18n'",
        content
    )
    
    # 2. 添加 useI18n 初始化
    content = re.sub(
        r"(const store = useLLMProvidersStore\(\))",
        r"const { t } = useI18n()\n\1",
        content
    )
    
    # 3. 替换模板中的中文
    replacements = [
        (r'路由器状态', r"{{ t('routerStatusPanel.title') }}"),
        (r'暂无路由器状态数据，请点击右上角刷新', r"{{ t('routerStatusPanel.emptyState') }}"),
        (r'当前路由策略', r"{{ t('routerStatusPanel.currentStrategy') }}"),
        (r'激活 Provider', r"{{ t('routerStatusPanel.activeProvider') }}"),
        (r'未激活', r"{{ t('routerStatusPanel.notActivated') }}"),
        (r'可用 Provider 数', r"{{ t('routerStatusPanel.availableProviders') }}"),
        (r'延迟样本总数', r"{{ t('routerStatusPanel.totalLatencySamples') }}"),
        (r'缓存命中率', r"{{ t('routerStatusPanel.cacheHitRate') }}"),
        (r'Fallback 链', r"{{ t('routerStatusPanel.fallbackChain') }}"),
        (r'无 Fallback 链', r"{{ t('routerStatusPanel.noFallbackChain') }}"),
        (r'切换策略：', r"{{ t('routerStatusPanel.switchStrategy') }}"),
        (r'选择路由策略', r"{{ t('routerStatusPanel.selectStrategy') }}"),
        (r'提示：当前仅显示状态，实际切换需后端支持', r"{{ t('routerStatusPanel.switchHint') }}"),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    # 4. 替换脚本中的中文
    script_replacements = [
        (r"description: '尚未加载路由器状态'", r"description: t('routerStatusPanel.notLoadedYet')"),
        (r"description: '未知策略'", r"description: t('routerStatusPanel.unknownStrategy')"),
    ]
    
    for old, new in script_replacements:
        content = re.sub(old, new, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新: {file_path}")


def update_auto_detect_panel():
    """修改 AutoDetectPanel.vue"""
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\settings\AutoDetectPanel.vue'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 添加 useI18n 导入
    content = re.sub(
        r"(import \{ computed \} from 'vue')",
        r"\1\nimport { useI18n } from 'vue-i18n'",
        content
    )
    
    # 2. 添加 useI18n 初始化
    content = re.sub(
        r"(const store = useLLMProvidersStore\(\))",
        r"const { t } = useI18n()\n\1",
        content
    )
    
    # 3. 替换模板中的中文
    replacements = [
        (r'自动探测本机 LLM 服务', r"{{ t('autoDetectPanel.title') }}"),
        (r'扫描本机', r"{{ t('autoDetectPanel.scanButton') }}"),
        (r'导入到注册表', r"{{ t('autoDetectPanel.importButton') }}"),
        (r'尚未执行扫描', r"{{ t('autoDetectPanel.emptyTitle') }}"),
        (r'点击"扫描本机"自动检测已安装的 LLM 服务（Ollama / LM Studio / llama.cpp / vLLM 等）。\s*扫描基于端口探测 \+ 进程名识别 \+ API 健康探测，<strong>不会修改任何配置</strong>。',
         r"{{ t('autoDetectPanel.emptyDescription') }}"),
        (r'正在扫描本机 LLM 服务...', r"{{ t('autoDetectPanel.scanningText') }}"),
        (r'扫描 \{\{ store\.detected\.length \}\} 项，命中 \{\{ detectedCount \}\} 项',
         r"{{ t('autoDetectPanel.scanResult', { total: store.detected.length, hit: detectedCount }) }}"),
        (r'耗时 \{\{ store\.lastDetectDuration \}\}ms',
         r"{{ t('autoDetectPanel.duration', { ms: store.lastDetectDuration }) }}"),
        (r'label="状态"', r':label="t(\'autoDetectPanel.colStatus\')"'),
        (r'在线', r"{{ t('autoDetectPanel.statusOnline') }}"),
        (r'离线', r"{{ t('autoDetectPanel.statusOffline') }}"),
        (r'label="类型"', r':label="t(\'autoDetectPanel.colType\')"'),
        (r'label="建议 ID"', r':label="t(\'autoDetectPanel.colSuggestedId\')"'),
        (r'label="Base URL"', r':label="t(\'autoDetectPanel.colBaseUrl\')"'),
        (r'label="默认模型"', r':label="t(\'autoDetectPanel.colDefaultModel\')"'),
        (r'label="探测方式"', r':label="t(\'autoDetectPanel.colDetectionMethod\')"'),
        (r'label="说明"', r':label="t(\'autoDetectPanel.colDescription\')"'),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    # 4. 替换脚本中的中文（ElMessageBox）
    script_replacements = [
        (r"'将把所有探测到的 LLM 服务导入到注册表（已存在同 ID 会被跳过），并自动激活第一个本地 Provider。继续？'",
         r"t('autoDetectPanel.importConfirmMessage')"),
        (r"'导入确认'", r"t('autoDetectPanel.importConfirmTitle')"),
        (r"confirmButtonText: '导入'", r"confirmButtonText: t('autoDetectPanel.import')"),
        (r"cancelButtonText: '取消'", r"cancelButtonText: t('autoDetectPanel.cancel')"),
    ]
    
    for old, new in script_replacements:
        content = re.sub(old, new, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新: {file_path}")


def update_zh_cn_locale():
    """更新 zh-CN.ts"""
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\locales\zh-CN.ts'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 在文件末尾的 } 之前添加新的翻译
    new_translations = """
  routerStatusPanel: {
    title: '路由器状态',
    emptyState: '暂无路由器状态数据，请点击右上角刷新',
    currentStrategy: '当前路由策略',
    activeProvider: '激活 Provider',
    notActivated: '未激活',
    availableProviders: '可用 Provider 数',
    totalLatencySamples: '延迟样本总数',
    cacheHitRate: '缓存命中率',
    fallbackChain: 'Fallback 链',
    noFallbackChain: '无 Fallback 链',
    switchStrategy: '切换策略：',
    selectStrategy: '选择路由策略',
    switchHint: '提示：当前仅显示状态，实际切换需后端支持',
    notLoadedYet: '尚未加载路由器状态',
    unknownStrategy: '未知策略',
  },
  autoDetectPanel: {
    title: '自动探测本机 LLM 服务',
    scanButton: '扫描本机',
    importButton: '导入到注册表',
    emptyTitle: '尚未执行扫描',
    emptyDescription: '点击"扫描本机"自动检测已安装的 LLM 服务（Ollama / LM Studio / llama.cpp / vLLM 等）。扫描基于端口探测 + 进程名识别 + API 健康探测，<strong>不会修改任何配置</strong>。',
    scanningText: '正在扫描本机 LLM 服务...',
    scanResult: '扫描 {total} 项，命中 {hit} 项',
    duration: '耗时 {ms}ms',
    colStatus: '状态',
    statusOnline: '在线',
    statusOffline: '离线',
    colType: '类型',
    colSuggestedId: '建议 ID',
    colBaseUrl: 'Base URL',
    colDefaultModel: '默认模型',
    colDetectionMethod: '探测方式',
    colDescription: '说明',
    importConfirmMessage: '将把所有探测到的 LLM 服务导入到注册表（已存在同 ID 会被跳过），并自动激活第一个本地 Provider。继续？',
    importConfirmTitle: '导入确认',
    import: '导入',
    cancel: '取消',
  },
"""
    
    # 在最后的 } 之前插入
    content = re.sub(r'(\n\}\n)$', new_translations + r'\1', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新: {file_path}")


def update_en_locale():
    """更新 en.ts"""
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\locales\en.ts'
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 在文件末尾的 } 之前添加新的翻译
    new_translations = """
  routerStatusPanel: {
    title: 'Router Status',
    emptyState: 'No router status data available, please click refresh in the top right',
    currentStrategy: 'Current Routing Strategy',
    activeProvider: 'Active Provider',
    notActivated: 'Not Activated',
    availableProviders: 'Available Providers',
    totalLatencySamples: 'Total Latency Samples',
    cacheHitRate: 'Cache Hit Rate',
    fallbackChain: 'Fallback Chain',
    noFallbackChain: 'No Fallback Chain',
    switchStrategy: 'Switch Strategy:',
    selectStrategy: 'Select routing strategy',
    switchHint: 'Note: Currently only displays status, actual switching requires backend support',
    notLoadedYet: 'Router status not loaded yet',
    unknownStrategy: 'Unknown strategy',
  },
  autoDetectPanel: {
    title: 'Auto-detect Local LLM Services',
    scanButton: 'Scan Local',
    importButton: 'Import to Registry',
    emptyTitle: 'Scan not performed yet',
    emptyDescription: 'Click "Scan Local" to automatically detect installed LLM services (Ollama / LM Studio / llama.cpp / vLLM, etc.). Scanning is based on port detection + process name identification + API health checks, <strong>no configurations will be modified</strong>.',
    scanningText: 'Scanning local LLM services...',
    scanResult: 'Scanned {total} items, hit {hit} items',
    duration: 'Duration: {ms}ms',
    colStatus: 'Status',
    statusOnline: 'Online',
    statusOffline: 'Offline',
    colType: 'Type',
    colSuggestedId: 'Suggested ID',
    colBaseUrl: 'Base URL',
    colDefaultModel: 'Default Model',
    colDetectionMethod: 'Detection Method',
    colDescription: 'Description',
    importConfirmMessage: 'All detected LLM services will be imported to the registry (existing IDs will be skipped), and the first local Provider will be automatically activated. Continue?',
    importConfirmTitle: 'Import Confirmation',
    import: 'Import',
    cancel: 'Cancel',
  },
"""
    
    # 在最后的 } 之前插入
    content = re.sub(r'(\n\}\n)$', new_translations + r'\1', content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ 已更新: {file_path}")


if __name__ == '__main__':
    print("开始 i18n 国际化改造...")
    print()
    
    try:
        update_router_status_panel()
        update_auto_detect_panel()
        update_zh_cn_locale()
        update_en_locale()
        
        print()
        print("=" * 60)
        print("✓ 所有文件已成功更新！")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
