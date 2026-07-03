# -*- coding: utf-8 -*-
import io

path = r"c:\Users\Lenovo\Desktop\" + chr(28789) + chr(22659) + chr(21046) + chr(36896) + chr(65288) + chr(19978) + chr(32447) + chr(29256) + chr(65289) + r"\src\locales\en.ts"
with io.open(path, "r", encoding="utf-8") as f:
    text = f.read()

new_block = """,
  // === UXDemo.vue UX demo page ===
  uxDemo: {
    pageTitle: "UX Feature Demo",
    btnStartTour: "Start Tour Guide",
    btnCommandPalette: "Command Palette (Ctrl+K)",
    statTourSteps: "Tour Steps",
    statExampleCount: "Example Projects",
    statCommandCount: "Registered Commands",
    sectionFeatures: "Implemented Features",
    featureTourLabel: "Tour Guide",
    featureGalleryLabel: "Example Projects",
    featureCommandLabel: "Command Palette",
    tagCompleted: "Completed",
    featureTourDesc: "5 steps, progress memory, responsive design",
    featureGalleryDesc: "12 examples, search filter, code preview, one-click copy",
    featureCommandDesc: "Shortcut activation, fuzzy search, smart sorting, usage frequency memory",
    sectionGalleryPreview: "Example Projects Preview",
    tourStep1Title: "Welcome to Lingjing Manufacturing System",
    tourStep1Desc: "This is an AI-driven 3D modeling and process planning system. Let us explore the main features through a few simple steps.",
    tourStep2Title: "File Management",
    tourStep2Desc: "Here you can create, open, and save project files, and import STEP and DXF format files.",
    tourStep3Title: "Navigation Menu",
    tourStep3Desc: "Through the top menu, you can quickly access core functional modules such as workspace, settings, and process planning.",
    tourStep4Title: "Command Palette",
    tourStep4Desc: "Press Ctrl+K to quickly activate the command palette, supporting fuzzy search and smart sorting to improve efficiency.",
    tourStep5Title: "Ready to Start",
    tourStep5Desc: "The tour is complete! You can restart it from the Help menu at any time. Now let us start exploring the powerful features of the system!",
    cmdNewProjectName: "New Project",
    cmdNewProjectDesc: "Create a new project",
    cmdOpenProjectName: "Open Project",
    cmdOpenProjectDesc: "Open an existing project",
    cmdSaveProjectName: "Save Project",
    cmdSaveProjectDesc: "Save the current project",
    cmdExportGCodeName: "Export G-Code",
    cmdExportGCodeDesc: "Export toolpath as G-Code file",
    cmdStartSimulationName: "Start Simulation",
    cmdStartSimulationDesc: "Begin machining process simulation",
    cmdAiFeatureName: "AI Feature Recognition",
    cmdAiFeatureDesc: "Use AI to auto-recognize machining features",
    cmdViewExamplesName: "View Examples",
    cmdViewExamplesDesc: "Browse the example project library",
    cmdOpenSettingsName: "System Settings",
    cmdOpenSettingsDesc: "Open the system settings page",
    categoryFile: "File",
    categoryToolpath: "Toolpath",
    categorySimulation: "Simulation",
    categoryAI: "AI",
    categoryHelp: "Help",
    categorySystem: "System",
    msgNewProjectTriggered: "New Project function triggered",
    msgOpenProjectTriggered: "Open Project function triggered",
    msgSaveProjectTriggered: "Save Project function triggered",
    msgExportGCodeTriggered: "Export G-Code function triggered",
    msgStartSimulationTriggered: "Start Simulation function triggered",
    msgAiFeatureTriggered: "AI Feature Recognition function triggered",
    msgViewExamplesTriggered: "View Examples function triggered",
    msgOpenSettingsTriggered: "System Settings function triggered",
    msgTourCompleted: "Tour completed!",
    msgTourSkipped: "Tour skipped (from step {step})",
  },
}
"""

# Remove the last closing brace and add new block
if text.endswith("}\n"):
    text = text[:-2] + new_block
elif text.endswith("}"):
    text = text[:-1] + new_block
else:
    text = text + new_block

with io.open(path, "w", encoding="utf-8") as f:
    f.write(text)

print("en.ts: uxDemo namespace added")
