#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

def update_auto_detect_panel():
    file_path = r'c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\settings\AutoDetectPanel.vue'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add useI18n import
    content = re.sub(
        r"(import \{ computed \} from 'vue')",
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
        (r'自动探测本机 LLM 服务', r"{{ t('autoDetectPanel.title') }}"),
        (r'扫描本机', r"{{ t('autoDetectPanel.scanButton') }}"),
        (r'导入到注册表', r"{{ t('autoDetectPanel.importButton') }}"),
        (r'尚未执行扫描', r"{{ t('autoDetectPanel.emptyTitle') }}"),
        (r'正在扫描本机 LLM 服务...', r"{{ t('autoDetectPanel.scanningText') }}"),
        (r'在线', r"{{ t('autoDetectPanel.statusOnline') }}"),
        (r'离线', r"{{ t('autoDetectPanel.statusOffline') }}"),
        (r'label="状态"', r':label="t(\'autoDetectPanel.colStatus\')"'),
        (r'label="类型"', r':label="t(\'autoDetectPanel.colType\')"'),
        (r'label="建议 ID"', r':label="t(\'autoDetectPanel.colSuggestedId\')"'),
        (r'label="默认模型"', r':label="t(\'autoDetectPanel.colDefaultModel\')"'),
        (r'label="探测方式"', r':label="t(\'autoDetectPanel.colDetectionMethod\')"'),
        (r'label="说明"', r':label="t(\'autoDetectPanel.colDescription\')"'),
    ]
    
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    # Replace complex template expressions
    content = re.sub(
        r'扫描 \{\{ store\.detected\.length \}\} 项，命中 \{\{ detectedCount \}\} 项',
        r"{{ t('autoDetectPanel.scanResult', { total: store.detected.length, hit: detectedCount }) }}",
        content
    )
    content = re.sub(
        r'耗时 \{\{ store\.lastDetectDuration \}\}ms',
        r"{{ t('autoDetectPanel.duration', { ms: store.lastDetectDuration }) }}",
        content
    )
    
    # Replace script Chinese text (ElMessageBox)
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
    print(f"Updated: {file_path}")

update_auto_detect_panel()
