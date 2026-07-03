#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

def update_router_status_panel():
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\settings\RouterStatusPanel.vue'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add useI18n import
    content = re.sub(
        r"(import \{ computed, ref, watch \} from 'vue')",
        r"\1\nimport { useI18n } from 'vue-i18n'",
        content
    )
    
    # Add useI18n initialization
    content = re.sub(
        r"(const store = useLLMProvidersStore\(\))",
        r"const { t } = useI18n()\n\1",
        content
    )
    
    # Replace template Chinese text
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
    
    # Replace script Chinese text
    script_replacements = [
        (r"description: '尚未加载路由器状态'", r"description: t('routerStatusPanel.notLoadedYet')"),
        (r"description: '未知策略'", r"description: t('routerStatusPanel.unknownStrategy')"),
    ]
    
    for old, new in script_replacements:
        content = re.sub(old, new, content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Updated: {file_path}")

update_router_status_panel()
