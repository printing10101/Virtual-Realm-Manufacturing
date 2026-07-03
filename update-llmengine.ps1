$file = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\src\components\settings\LLMEngineSettings.vue"
$content = Get-Content $file -Raw -Encoding UTF8

# Add useI18n import
$content = $content -replace "import \{ ElMessageBox \} from 'element-plus'", "import { useI18n } from 'vue-i18n'`nimport { ElMessageBox } from 'element-plus'"

# Add const { t } = useI18n()
$content = $content -replace "const store = useLLMProvidersStore\(\)", "const { t } = useI18n()`nconst store = useLLMProvidersStore()"

# Replace template Chinese text
$content = $content -replace "AI 引擎状态", "{{ t('llmEngineSettings.aiEngineStatus') }}"
$content = $content -replace "\{\{ store\.hasActiveProvider \? '已激活' : '未激活' \}\}", "{{ store.hasActiveProvider ? t('llmEngineSettings.activated') : t('llmEngineSettings.notActivated') }}"
$content = $content -replace "\{\{ store\.encryptionAvailable \? '加密存储' : '明文存储' \}\}", "{{ store.encryptionAvailable ? t('llmEngineSettings.encryptedStorage') : t('llmEngineSettings.plaintextStorage') }}"
$content = $content -replace ">Provider 总数<", ">{{ t('llmEngineSettings.totalProviders') }}<"
$content = $content -replace ">已启用<", ">{{ t('llmEngineSettings.enabled') }}<"
$content = $content -replace ">本地 Provider<", ">{{ t('llmEngineSettings.localProviders') }}<"
$content = $content -replace ">云端 Provider<", ">{{ t('llmEngineSettings.cloudProviders') }}<"
$content = $content -replace ">当前激活 Provider<", ">{{ t('llmEngineSettings.currentActiveProvider') }}<"
$content = $content -replace ">未设置激活 Provider<", ">{{ t('llmEngineSettings.noActiveProvider') }}<"
$content = $content -replace ">配置存储路径<", ">{{ t('llmEngineSettings.configStoragePath') }}<"
$content = $content -replace ">Provider 列表<", ">{{ t('llmEngineSettings.providerList') }}<"
$content = $content -replace "新增 Provider", "{{ t('llmEngineSettings.addProvider') }}"

# Replace confirm dialog
$content = $content -replace "确认删除 Provider `"\$\{provider\.name\}`" \(\$\{provider\.provider_id\}\)？该操作不可撤销。", "{{ t('llmEngineSettings.confirmDeleteMessage', { name: provider.name, id: provider.provider_id }) }}"
$content = $content -replace "`'删除确认`'", "t('llmEngineSettings.deleteConfirmTitle')"
$content = $content -replace "confirmButtonText: '删除'", "confirmButtonText: t('llmEngineSettings.btnDelete')"
$content = $content -replace "cancelButtonText: '取消'", "cancelButtonText: t('llmEngineSettings.btnCancel')"

[System.IO.File]::WriteAllText($file, $content, [System.Text.UTF8Encoding]::new($false))
Write-Host "LLMEngineSettings.vue updated"
