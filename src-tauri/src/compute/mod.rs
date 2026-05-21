//! 灵境制造 Rust核心计算引擎 — 接口定义层
//!
//! 此模块定义了机床加工仿真与路径计算的核心Rust接口。
//! 当前Python仿真模块(voxel_cutter.py, collision_detector.py, toolpath_parser.py)
//! 将分阶段迁移至此，利用Rust的所有权模型和零成本抽象实现高性能计算。
//!
//! # 迁移路线图
//!
//! Phase 1 (当前): 接口定义 — 定义所有数据结构和FFI边界
//! Phase 2: VoxelCutter — 体素化切削仿真(à la voxel_cutter.py)
//! Phase 3: CollisionDetector — AABB碰撞检测(à la collision_detector.py)
//! Phase 4: ToolpathParser — G代码解析(à la toolpath_parser.py)
//!
//! # 与Python的交互协议
//!
//! 通过 Tauri Command (IPC) 与前端通信，通过 PyO3 与Python后端互操作:
//! - Python -> Rust: 通过 PyO3 将 NumPy 数组零拷贝传递
//! - Rust -> Python: 返回计算结果结构体，由 Python 序列化为 API 响应
//! - Rust -> 前端: 通过 Tauri invoke 直接发送仿真状态更新

pub mod collision;
pub mod toolpath;
pub mod types;
pub mod voxel;
