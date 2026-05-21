//! 数控加工仿真核心类型定义
//!
//! 定义与Python端对等的领域数据结构。
//! 命名遵循制造业行业标准(ISO 13399/841/230)。

use serde::{Deserialize, Serialize};

/// 机床物理约束(ISO 841/230)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MachineConstraint {
    /// 主轴功率(kW), 范围 [0.1, 200]
    pub spindle_power_kw: f64,
    /// 主轴扭矩(Nm), 范围 [0, 2000]
    pub spindle_torque_nm: f64,
    /// 主轴转速范围(RPM), [min, max]
    pub spindle_speed_rpm: [f64; 2],
    /// 快速横移XY(mm/min), G00速度
    pub rapid_traverse_xy_mm_min: f64,
    /// 快速横移Z(mm/min)
    pub rapid_traverse_z_mm_min: f64,
    /// 最大切削进给(mm/min)
    pub feed_cutting_max_mm_min: f64,
    /// 最大切削力(N)
    pub max_cutting_force_n: f64,
    /// 最大工件重量(kg)
    pub max_workpiece_weight_kg: f64,
    /// 定位精度(mm), ISO 230-2
    pub positioning_accuracy_mm: f64,
    /// 重复定位精度(mm)
    pub repeatability_mm: f64,
}

/// 刀具物理约束(ISO 13399)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolConstraint {
    pub diameter_mm: f64,
    pub cutting_length_mm: f64,
    pub overall_length_mm: f64,
    pub corner_radius_mm: f64,
    pub flute_count: u32,
    pub helix_angle_deg: f64,
    pub clearance_angle_deg: f64,
    pub max_depth_of_cut_mm: f64,
    pub max_cutting_force_n: f64,
    pub max_spindle_speed_rpm: f64,
    pub shank_diameter_mm: f64,
}

/// 材料物理约束(ISO 4957/683)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MaterialConstraint {
    pub hardness_hb: f64,
    pub tensile_strength_mpa: f64,
    pub yield_strength_mpa: f64,
    pub elongation_pct: f64,
    pub density_gcm3: f64,
    pub thermal_conductivity_w_mk: f64,
    pub specific_cutting_force_kc1_1: f64,
    pub machinability_index: f64,
    pub taylor_tool_life_exponent: f64,
    pub taylor_constant_c: f64,
}

/// 3D点/向量
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct Point3D {
    pub x: f64,
    pub y: f64,
    pub z: f64,
}

/// 轴对齐包围盒 (AABB)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AABB {
    pub min: Point3D,
    pub max: Point3D,
}

impl AABB {
    pub fn intersects(&self, other: &AABB) -> bool {
        self.min.x <= other.max.x
            && self.max.x >= other.min.x
            && self.min.y <= other.max.y
            && self.max.y >= other.min.y
            && self.min.z <= other.max.z
            && self.max.z >= other.min.z
    }

    pub fn contains_point(&self, point: &Point3D) -> bool {
        point.x >= self.min.x
            && point.x <= self.max.x
            && point.y >= self.min.y
            && point.y <= self.max.y
            && point.z >= self.min.z
            && point.z <= self.max.z
    }
}

/// 碰撞事件类型
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CollisionType {
    RapidIntoStock,
    RapidZLow,
    OvercutZ,
    ToolWorkpieceContact,
}

/// 碰撞严重程度
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CollisionSeverity {
    None,
    Warning,
    High,
    Critical,
}

/// 单个碰撞事件
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollisionEvent {
    pub collision_type: CollisionType,
    pub severity: CollisionSeverity,
    pub block_number: u32,
    pub position: Point3D,
    pub message: String,
    pub suggestion: String,
}

/// 碰撞检测报告
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CollisionReport {
    pub total_segments: u32,
    pub segments_checked: u32,
    pub collisions: Vec<CollisionEvent>,
    pub warnings: Vec<String>,
    pub safe: bool,
}

/// 体素切削仿真结果
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoxelSimulationResult {
    pub voxel_count: u64,
    pub removed_voxel_count: u64,
    pub voxel_size_mm: f64,
    pub duration_seconds: f64,
    pub collision_count: u32,
}
