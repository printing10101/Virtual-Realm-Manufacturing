#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete i18n update for ProviderList.vue, StepCard.vue, and locale files
"""

import os

BASE_DIR = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\src"

def update_provider_list():
    """Update ProviderList.vue with i18n"""
    filepath = os.path.join(BASE_DIR, "components", "settings", "ProviderList.vue")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add useI18n import
    if "import { useI18n } from 'vue-i18n'" not in content:
        content = content.replace(
            "import { computed } from 'vue'",
            "import { computed } from 'vue'\nimport { useI18n } from 'vue-i18n'"
        )
    
    # Add const { t } = useI18n()
    if "const { t } = useI18n()" not in content:
        content = content.replace(
            "defineProps<{",
            "const { t } = useI18n()\n\ndefineProps<{"
        )
    
    # Replace hardcoded Chinese in template
    replacements = {
        'title="尚未配置任何 Provider"': ':title="t(\'providerList.emptyTitle\')"',
        '当前未配置任何 LLM Provider。可点击上方"新增 Provider"手动添加，': '{{ t(\'providerList.emptyDescription\') }}',
        '或使用自动探测扫描本机已安装的 LLM 服务。': '',
        'label="状态"': ':label="t(\'providerList.colStatus\')"',
        '>激活\n            </el-tag>': '>{{ t(\'providerList.statusActive\') }}\n            </el-tag>',
        '>已启用\n            </el-tag>': '>{{ t(\'providerList.statusEnabled\') }}\n            </el-tag>',
        '>已禁用\n            </el-tag>': '>{{ t(\'providerList.statusDisabled\') }}\n            </el-tag>',
        'label="名称"': ':label="t(\'providerList.colName\')"',
        'label="类型"': ':label="t(\'providerList.colType\')"',
        "{{ getCategory(row.provider_type) === 'local' ? '本地' : '云端' }}": "{{ getCategory(row.provider_type) === 'local' ? t('providerList.typeLocal') : t('providerList.typeCloud') }}",
        'label="默认模型"': ':label="t(\'providerList.colDefaultModel\')"',
        'label="优先级"': ':label="t(\'providerList.colPriority\')"',
        'label="最近延迟"': ':label="t(\'providerList.colLastLatency\')"',
        'label="操作"': ':label="t(\'providerList.colActions\')"',
        '>激活\n            </el-button>': '>{{ t(\'providerList.btnActivate\') }}\n            </el-button>',
        "{{ row.enabled ? '禁用' : '启用' }}": "{{ row.enabled ? t('providerList.btnDisable') : t('providerList.btnEnable') }}",
        '>健康检查\n            </el-button>': '>{{ t(\'providerList.btnHealthCheck\') }}\n            </el-button>',
        '>更多<el-icon': '>{{ t(\'providerList.btnMore\') }}<el-icon',
        '>编辑配置\n                  </el-dropdown-item>': '>{{ t(\'providerList.btnEditConfig\') }}\n                  </el-dropdown-item>',
        '>查看模型\n                  </el-dropdown-item>': '>{{ t(\'providerList.btnViewModels\') }}\n                  </el-dropdown-item>',
        '>调用测试\n                  </el-dropdown-item>': '>{{ t(\'providerList.btnTestCall\') }}\n                  </el-dropdown-item>',
        'color: var(--el-color-danger)">删除</span>': 'color: var(--el-color-danger)">{{ t(\'providerList.btnDelete\') }}</span>',
    }
    
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    
    print(f"✓ Updated {filepath}")


def update_step_card():
    """Update StepCard.vue with i18n"""
    filepath = os.path.join(BASE_DIR, "components", "ReasoningTrace", "StepCard.vue")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add useI18n import
    if "import { useI18n } from 'vue-i18n'" not in content:
        content = content.replace(
            "import { computed } from 'vue'",
            "import { computed } from 'vue'\nimport { useI18n } from 'vue-i18n'"
        )
    
    # Add const { t } = useI18n()
    if "const { t } = useI18n()" not in content:
        content = content.replace(
            "const props = defineProps<{",
            "const { t } = useI18n()\n\nconst props = defineProps<{"
        )
    
    # Replace hardcoded Chinese in template
    replacements = {
        '>匹配规则\n          </div>': '>{{ t(\'stepCard.matchingRules\') }}\n          </div>',
        '>相似案例\n          </div>': '>{{ t(\'stepCard.similarCases\') }}\n          </div>',
        '>校验参数\n          </div>': '>{{ t(\'stepCard.validationParams\') }}\n          </div>',
        'label="参数"': ':label="t(\'stepCard.colParam\')"',
        'label="值"': ':label="t(\'stepCard.colValue\')"',
        'label="阈值"': ':label="t(\'stepCard.colThreshold\')"',
        'label="结果"': ':label="t(\'stepCard.colResult\')"',
        "{{ row.passed ? '通过' : '失败' }}": "{{ row.passed ? t('stepCard.resultPass') : t('stepCard.resultFail') }}",
        '>物理公式\n          </div>': '>{{ t(\'stepCard.physicsFormulas\') }}\n          </div>',
        '>学习曲线\n          </div>': '>{{ t(\'stepCard.learningCurve\') }}\n          </div>',
        '>最终 Loss:': '>{{ t(\'stepCard.finalLoss\') }}:',
        '>样本对比\n          </div>': '>{{ t(\'stepCard.sampleComparison\') }}\n          </div>',
        '>特征维度:': '>{{ t(\'stepCard.featureDimensions\') }}:',
        '>置信度</span>': '>{{ t(\'stepCard.confidence\') }}</span>',
    }
    
    for old, new in replacements.items():
        content = content.replace(old, new)
    
    # Replace statusText computed property
    old_status = """const statusText = computed(() => {
  switch (props.step.status) {
    case 'pending':
      return '待执行'
    case 'running':
      return '执行中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    case 'skipped':
      return '已跳过'
    default:
      return '未知'
  }
})"""
    
    new_status = """const statusText = computed(() => {
  switch (props.step.status) {
    case 'pending':
      return t('stepCard.statusPending')
    case 'running':
      return t('stepCard.statusRunning')
    case 'completed':
      return t('stepCard.statusCompleted')
    case 'failed':
      return t('stepCard.statusFailed')
    case 'skipped':
      return t('stepCard.statusSkipped')
    default:
      return t('stepCard.statusUnknown')
  }
})"""
    
    content = content.replace(old_status, new_status)
    
    with open(filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    
    print(f"✓ Updated {filepath}")


def update_locale_files():
    """Update zh-CN.ts and en.ts with new translation keys"""
    
    # zh-CN.ts additions
    zh_cn_additions = """
  // === LLMEngineSettings.vue LLM引擎设置 ===
  llmEngineSettings: {
    aiEngineStatus: "AI 引擎状态",
    activated: "已激活",
    notActivated: "未激活",
    encryptedStorage: "加密存储",
    plaintextStorage: "明文存储",
    totalProviders: "Provider 总数",
    enabled: "已启用",
    localProviders: "本地 Provider",
    cloudProviders: "云端 Provider",
    currentActiveProvider: "当前激活 Provider",
    noActiveProvider: "未设置激活 Provider",
    configStoragePath: "配置存储路径",
    providerList: "Provider 列表",
    addProvider: "新增 Provider",
    confirmDeleteMessage: "确认删除 Provider \\"{name}\\" ({id})？该操作不可撤销。",
    deleteConfirmTitle: "删除确认",
    btnDelete: "删除",
    btnCancel: "取消",
  },
  // === ProviderList.vue Provider列表 ===
  providerList: {
    emptyTitle: "尚未配置任何 Provider",
    emptyDescription: "当前未配置任何 LLM Provider。可点击上方\\"新增 Provider\\"手动添加，或使用自动探测扫描本机已安装的 LLM 服务。",
    colStatus: "状态",
    statusActive: "激活",
    statusEnabled: "已启用",
    statusDisabled: "已禁用",
    colName: "名称",
    colType: "类型",
    typeLocal: "本地",
    typeCloud: "云端",
    colBaseUrl: "Base URL",
    colDefaultModel: "默认模型",
    colPriority: "优先级",
    colLastLatency: "最近延迟",
    colActions: "操作",
    btnActivate: "激活",
    btnDisable: "禁用",
    btnEnable: "启用",
    btnHealthCheck: "健康检查",
    btnMore: "更多",
    btnEditConfig: "编辑配置",
    btnViewModels: "查看模型",
    btnTestCall: "调用测试",
    btnDelete: "删除",
  },
  // === StepCard.vue 推理步骤卡片 ===
  stepCard: {
    statusPending: "待执行",
    statusRunning: "执行中",
    statusCompleted: "已完成",
    statusFailed: "失败",
    statusSkipped: "已跳过",
    statusUnknown: "未知",
    matchingRules: "匹配规则",
    similarCases: "相似案例",
    validationParams: "校验参数",
    physicsFormulas: "物理公式",
    learningCurve: "学习曲线",
    sampleComparison: "样本对比",
    colParam: "参数",
    colValue: "值",
    colThreshold: "阈值",
    colResult: "结果",
    resultPass: "通过",
    resultFail: "失败",
    confidence: "置信度",
    finalLoss: "最终 Loss",
    featureDimensions: "特征维度",
  },"""
    
    # en.ts additions
    en_additions = """
  // === LLMEngineSettings.vue LLM Engine Settings ===
  llmEngineSettings: {
    aiEngineStatus: "AI Engine Status",
    activated: "Activated",
    notActivated: "Not Activated",
    encryptedStorage: "Encrypted Storage",
    plaintextStorage: "Plaintext Storage",
    totalProviders: "Total Providers",
    enabled: "Enabled",
    localProviders: "Local Providers",
    cloudProviders: "Cloud Providers",
    currentActiveProvider: "Current Active Provider",
    noActiveProvider: "No Active Provider",
    configStoragePath: "Config Storage Path",
    providerList: "Provider List",
    addProvider: "Add Provider",
    confirmDeleteMessage: "Confirm delete Provider \\"{name}\\" ({id})? This action cannot be undone.",
    deleteConfirmTitle: "Delete Confirmation",
    btnDelete: "Delete",
    btnCancel: "Cancel",
  },
  // === ProviderList.vue Provider List ===
  providerList: {
    emptyTitle: "No Provider Configured",
    emptyDescription: "No LLM Provider is currently configured. Click \\"Add Provider\\" above to add manually, or use auto-detection to scan locally installed LLM services.",
    colStatus: "Status",
    statusActive: "Active",
    statusEnabled: "Enabled",
    statusDisabled: "Disabled",
    colName: "Name",
    colType: "Type",
    typeLocal: "Local",
    typeCloud: "Cloud",
    colBaseUrl: "Base URL",
    colDefaultModel: "Default Model",
    colPriority: "Priority",
    colLastLatency: "Last Latency",
    colActions: "Actions",
    btnActivate: "Activate",
    btnDisable: "Disable",
    btnEnable: "Enable",
    btnHealthCheck: "Health Check",
    btnMore: "More",
    btnEditConfig: "Edit Config",
    btnViewModels: "View Models",
    btnTestCall: "Test Call",
    btnDelete: "Delete",
  },
  // === StepCard.vue Reasoning Step Card ===
  stepCard: {
    statusPending: "Pending",
    statusRunning: "Running",
    statusCompleted: "Completed",
    statusFailed: "Failed",
    statusSkipped: "Skipped",
    statusUnknown: "Unknown",
    matchingRules: "Matching Rules",
    similarCases: "Similar Cases",
    validationParams: "Validation Params",
    physicsFormulas: "Physics Formulas",
    learningCurve: "Learning Curve",
    sampleComparison: "Sample Comparison",
    colParam: "Param",
    colValue: "Value",
    colThreshold: "Threshold",
    colResult: "Result",
    resultPass: "Pass",
    resultFail: "Fail",
    confidence: "Confidence",
    finalLoss: "Final Loss",
    featureDimensions: "Feature Dimensions",
  },"""
    
    # Update zh-CN.ts
    zh_filepath = os.path.join(BASE_DIR, "locales", "zh-CN.ts")
    with open(zh_filepath, 'r', encoding='utf-8') as f:
        zh_content = f.read()
    
    # Find the last } and insert before it
    last_brace = zh_content.rfind('}')
    if last_brace != -1:
        zh_content = zh_content[:last_brace] + zh_cn_additions + '\n' + zh_content[last_brace:]
    
    with open(zh_filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(zh_content)
    
    print(f"✓ Updated {zh_filepath}")
    
    # Update en.ts
    en_filepath = os.path.join(BASE_DIR, "locales", "en.ts")
    with open(en_filepath, 'r', encoding='utf-8') as f:
        en_content = f.read()
    
    # Find the last } and insert before it
    last_brace = en_content.rfind('}')
    if last_brace != -1:
        en_content = en_content[:last_brace] + en_additions + '\n' + en_content[last_brace:]
    
    with open(en_filepath, 'w', encoding='utf-8', newline='\n') as f:
        f.write(en_content)
    
    print(f"✓ Updated {en_filepath}")


if __name__ == "__main__":
    print("Starting i18n update...")
    update_provider_list()
    update_step_card()
    update_locale_files()
    print("\n✅ All i18n updates completed!")
