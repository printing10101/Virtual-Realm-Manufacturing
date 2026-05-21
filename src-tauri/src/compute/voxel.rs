//! 体素化切削仿真引擎 (Rust)
//!
//! 目标：替代 python/app/simulation/voxel_cutter.py。
//! 利用 Rust 的 Vec<u8> 位数组和多线程并行化实现高性能材料去除仿真。
//!
//! 迁移理由（为什么要在Rust而非Python中实现）:
//! - 体素化是 O(N*V*T) 的嵌套循环，其中N=刀位点、V=体素、T=刀具体素
//! - Python的for循环比Rust慢50-100倍
//! - Rust可安全使用 SIMD (portable_simd) 进行批量体素操作
//! - Rust的所有权模型天然适合 voxel_grid 的原地修改
//!
//! # 实现说明
//!
//! 迁移时保持与 Python ToolModel 和 VoxelCutter 接口兼容。
//! Python 端通过 PyO3 调用，参数以 NumPy 数组零拷贝传递。
//!
//! Python调用模式(迁移后):
//! ```python
//! from lingjing_compute import VoxelCutter  # Rust-backed
//! cutter = VoxelCutter(voxel_size=1.0)
//! result = cutter.run_simulation(stl_bytes, tool_params, segments)
//! ```

// Placeholder: will be implemented in Phase 2
