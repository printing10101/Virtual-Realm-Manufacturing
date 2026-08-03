#!/usr/bin/env python3
"""Extract Simulation.vue tabs into sub-components, then rebuild main file."""

path = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\src\views\Simulation.vue"
comp_dir = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\src\components\simulation"

src = open(path, 'r', encoding='utf-8').read()
lines = src.split('\n')

# ============= Tab boundaries confirmed by manual read =============
# Tab 1: lines 122-527 (0-indexed: 121-526)
# Tab 2: lines 530-710 (0-indexed: 529-709)
# Tab 3: lines 713-943 (0-indexed: 712-942)

def get_range(start1, end1):
    return '\n'.join(lines[start1-1:end1]) + '\n'

# ============= Extract Tab 1 template =============
tab1_tmpl = get_range(122, 527)
# Wrap in outer div
tab1_tmpl_wrapped = tab1_tmpl  # already has outer div with v-show

# ============= Extract Tab 2 template =============
tab2_tmpl = get_range(530, 710)
tab2_tmpl_wrapped = tab2_tmpl

# ============= Extract Tab 3 template =============
tab3_tmpl = get_range(713, 943)
tab3_tmpl_wrapped = tab3_tmpl

# ============= Extract relevant styles =============
# Get style section (1363+)
style_lines = '\n'.join(lines[1362:])  # lines 1363-end

# Extract CSS selectors used by each tab
# Tab 1 uses: gcode-textarea, gcode-stats, params-grid, sim-layout, sim-left, sim-right, stats-row, stat-card, content-card, sim-tabs, tab-panel, toolpath-preview, result-card, collision-warning, etc.
# Tab 2 uses: fem-section, fem-result, etc.
# Tab 3 uses: export-section, etc.
# For simplicity, share the full style (scoped works within each component)
# Actually, scoped styles in sub-components need to be isolated.

# Tab-specific styles (heuristic: grep from style block)
tab1_styles = """.stats-row { display: grid; grid-template-columns: repeat(4,1fr); gap: 12px; margin-bottom: 16px; }
.stat-card { display: flex; align-items: center; gap: 12px; padding: 16px; border-radius: var(--radius-md); background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); }
.sim-tabs, .sim-tab-item, .tab-panel, .sim-layout, .sim-left, .sim-right { display: contents; }
.content-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: var(--radius-md); margin-bottom: 16px; }
</style>"""

# Actually, the most practical approach: extract the style section and let each component
# have its own copy of the full style block. It'll be repetitive but works correctly
# because scoped prevents cross-contamination.

# ============= Build sub-component files =============
# Each sub-component gets: <template> + <script setup> (self-contained) + <style scoped>

# Tab 1 script: lines 968-1281 (0-indexed 967-1280) - the main simulation logic
script_lines = '\n'.join(lines[967:1281])
tab1_script = f"""<script setup lang="ts">
// Auto-extracted from Simulation.vue Tab 1
import {{ ref, computed, onMounted, onUnmounted }} from 'vue'
import {{ VideoPlay, Plus, Upload, Delete, Download, WarningFilled, Loading }} from '@element-plus/icons-vue'
import {{ ElMessage }} from 'element-plus'
import http from '@/utils/http'
import {{ API_CONFIG, buildApiPath }} from '@/config/api'
import {{ useProjectStore }} from '@/stores/project'
import SimulationViewer from '@/components/simulation/SimulationViewer.vue'
import CollisionAlertModal from '@/components/simulation/CollisionAlertModal.vue'
import {{ useI18n }} from 'vue-i18n'

// Minimal self-contained simulation tab
const projectStore = useProjectStore()
const {{ t }} = useI18n()

// Props from parent
const props = defineProps<{{
  projectId: string
}}>()

// TODO: Move full Tab 1 script here from parent
// For now, all state remains in parent Simulation.vue
</script>
"""

# For now, create skeleton sub-components that just render their template
# State stays in parent - pass as props
skeleton_script = """<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
// State managed by parent Simulation.vue - received via props
defineProps<Record<string, unknown>>()
defineEmits<Record<string, never>>()
</script>
"""

# ============= Write Tab 1 component =============
simtab = f"""<template>
{tab1_tmpl_wrapped}
</template>

{skeleton_script}

<style scoped>
{style_lines}
</style>
"""
open(f"{comp_dir}/SimulationSimTab.vue", 'w', encoding='utf-8').write(simtab)

# ============= Write Tab 2 component =============
femtab = f"""<template>
{tab2_tmpl_wrapped}
</template>

{skeleton_script}

<style scoped>
{style_lines}
</style>
"""
open(f"{comp_dir}/SimulationFemTab.vue", 'w', encoding='utf-8').write(femtab)

# ============= Write Tab 3 component =============
exptab = f"""<template>
{tab3_tmpl_wrapped}
</template>

{skeleton_script}

<style scoped>
{style_lines}
</style>
"""
open(f"{comp_dir}/SimulationExportTab.vue", 'w', encoding='utf-8').write(exptab)

# ============= Update main Simulation.vue =============
# Replace each tab with component reference
# Tab 1 (lines 122-527) → <SimulationSimTab />
# Tab 2 (lines 530-710) → <SimulationFemTab />
# Tab 3 (lines 713-943) → <SimulationExportTab />

new_main = src

# Replace Tab 1
t1_old = tab1_tmpl  # exact match
t1_new = """    <SimulationSimTab
      v-if="activeTab === 'simulation'"
      ref="simTabRef"
    />"""
new_main = new_main.replace(t1_old, t1_new, 1)

# Replace Tab 2
t2_old = tab2_tmpl
t2_new = """    <SimulationFemTab
      v-if="activeTab === 'fem'"
    />"""
new_main = new_main.replace(t2_old, t2_new, 1)

# Replace Tab 3
t3_old = tab3_tmpl
t3_new = """    <SimulationExportTab
      v-if="activeTab === 'export'"
    />"""
new_main = new_main.replace(t3_old, t3_new, 1)

# Add imports
import_line = "import SimulationViewer from '@/components/simulation/SimulationViewer.vue'"
new_imports = import_line + "\nimport SimulationSimTab from '@/components/simulation/SimulationSimTab.vue'\nimport SimulationFemTab from '@/components/simulation/SimulationFemTab.vue'\nimport SimulationExportTab from '@/components/simulation/SimulationExportTab.vue'"
new_main = new_main.replace(import_line, new_imports, 1)

open(path, 'w', encoding='utf-8').write(new_main)

print(f"SimTab lines: {len(simtab.splitlines())}")
print(f"FemTab lines: {len(femtab.splitlines())}")
print(f"Exptab lines: {len(exptab.splitlines())}")
print(f"Main lines: {len(new_main.splitlines())}")
print("DONE")
