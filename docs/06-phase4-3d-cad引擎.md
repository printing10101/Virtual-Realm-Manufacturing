# Phase 4: 3D/CAD 引擎

> **预计工期**: 5-6 小时 | **前置依赖**: Phase 2 | **下一步**: Phase 5 - PhyCo-Agent 架构

## 目标

实现完整的 3D/CAD 引擎功能，包括三视图生成器、CadQuery 参数化生成器、Three.js 3D 查看器组件，以及前端三视图上传页面。

## 验证标准

- [ ] `POST /api/cad/three-view-to-3d` 创建三视图生成任务
- [ ] `GET /api/cad/tasks/{task_id}` 查询任务状态
- [ ] `POST /api/cad/cadquery` 生成 CadQuery 脚本
- [ ] Three.js 查看器组件可渲染 STL/OBJ/GLTF 模型
- [ ] 前端 MultiViewTo3D.vue 可上传三视图并查看生成结果

---

## 核心组件

### 三视图生成器 (`python/app/cad/generator.py`)

```python
async def generate_from_three_views(request: ThreeViewTaskRequest) -> dict
```

API 路由：
- `POST /api/cad/three-view-to-3d` - 创建生成任务
- `GET /api/cad/tasks/{task_id}` - 查询任务状态
- `GET /api/cad/models/{model_id}/download` - 下载生成的模型

### CadQuery 生成器 (`python/app/cad/cadquery_gen.py`)

```python
async def generate_cadquery(request: CadQueryRequest) -> dict
```

### Three.js 查看器 (`src/components/three/ThreeViewer.vue`)

功能：
- 渲染 STL/OBJ/GLTF 格式模型
- 轨道控制（旋转、缩放、平移）
- 模型材质显示
- 网格/线框模式切换

### 前端页面 (`src/views/MultiViewTo3D.vue`)

功能：
- 三视图图片上传
- 生成任务触发
- 实时进度显示
- 3D 预览展示

---

## 验证清单

1. 三视图生成 API 正常工作
2. CadQuery 生成 API 正常工作
3. Three.js 查看器可渲染模型
4. 前端页面完整实现
5. 模型下载功能正常

---

## 相关文档

- [Phase 2 - Python AI 后端](../04-Phase2-Python-AI后端.md)
- [Phase 5 - PhyCo-Agent 架构](../07-Phase5-AI工作流.md)
