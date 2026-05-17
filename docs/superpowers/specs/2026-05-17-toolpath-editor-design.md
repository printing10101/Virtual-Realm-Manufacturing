# 交互式刀路编辑器 - 设计规范

> 版本: 1.0 | 日期: 2026-05-17 | 状态: 已确认

## 架构方案: 方案A - 独立编辑器页面

### 目录结构
```
src/components/toolpath-editor/
├── ToolpathEditor.vue           # 主页面
├── ToolpathCanvas.vue           # Three.js 3D渲染+交互
├── RightClickMenu.vue           # 右键上下文菜单
├── FeedRateDialog.vue           # 进给率调整对话框
├── GCodeExportDialog.vue        # G代码导出（多格式）
├── ToolpathImportDialog.vue     # 独立G代码导入
├── composables/
│   ├── useToolpathInteraction.ts  # Raycaster悬停/拾取
│   └── useGCodeParser.ts          # G代码文本解析
├── commands/
│   ├── BaseCommand.ts
│   ├── DeleteSegmentCommand.ts
│   ├── ModifyFeedRateCommand.ts
│   └── CommandHistory.ts
├── stores/
│   └── toolpathEditor.ts          # Pinia Store
├── types/
│   └── editor.ts                  # 编辑专用类型
└── __tests__/
    ├── toolpathEditor.test.ts
    ├── CommandHistory.test.ts
    ├── useGCodeParser.test.ts
    └── ToolpathCanvas.test.ts
```

### 数据模型
- **EditableToolpathSegment**: 扩展 ToolpathSegmentData，新增 id/uuid、feedRate、spindleSpeed、toolId、isDeleted
- **Pinia Store**: 集中管理 segments[]、originalSegments[]、选中/悬停状态、isDirty、CommandHistory

### 交互流程
1. 悬停: Raycaster → 高亮段 (颜色#ffd740, 线宽2, <100ms)
2. 右键: Raycaster拾取 → 上下文菜单 (删除此段/调整进给率)
3. 编辑: Command.execute() → Pinia Store更新 → 3D重绘
4. 撤销/重做: CommandHistory.undo()/redo() → 50步上限
5. 导出: segments → G代码文本 (Fanuc/Siemens/Heidenhain)

### 命令模式
- 抽象基类 BaseCommand { execute(), undo() }
- DeleteSegmentCommand: 记录 segmentIndex + 完整 segment 数据
- ModifyFeedRateCommand: 记录 segmentIndex + oldRate + newRate
- CommandHistory: 双栈 (undoStack/redoStack)，maxSize=50

### 性能目标
- 悬停响应 <100ms
- 10000+ 刀位点场景 ≥30fps
- BufferGeometry 分段渲染，实例化材质

### G代码导出
- 多格式: Fanuc 0i / Siemens 840D / Heidenhain TNC
- 使用项目现有后处理器前端逻辑重建G代码行
- 导出前验证: 检查必填字段、数值范围
