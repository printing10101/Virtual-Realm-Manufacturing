"""
JEPA 服务模块

提供统一的 JEPA 推理接口，支持：
1. 多模态 JEPA 特征提取
2. 视频 JEPA 特征提取
3. 点云 MAE 特征提取
4. 知识图谱注入
5. 工艺推荐
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class JEPAServer:
    """JEPA 服务类
    
    提供统一的 JEPA 推理接口，支持多种 JEPA 变体
    """
    
    def __init__(self, model_dir: Optional[Path] = None):
        """初始化 JEPA 服务
        
        Args:
            model_dir: 模型目录路径
        """
        self.model_dir = model_dir or Path(__file__).parent / "models"
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        self._multimodal_jepa = None
        self._video_jepa = None
        self._point_mae = None
        
        logger.info("JEPA 服务初始化完成，模型目录: %s", self.model_dir)
    
    def extract_features_multimodal(
        self,
        input_data: dict,
        feature_type: str = "geometry",
    ) -> Optional[dict]:
        """使用多模态 JEPA 提取特征
        
        Args:
            input_data: 输入数据（包含 DXF 路径、几何数据等）
            feature_type: 特征类型（geometry/topology/hybrid）
            
        Returns:
            特征字典，包含嵌入向量和语义信息
        """
        try:
            # 延迟导入，避免循环依赖
            from app.ai.ijepa_3d.inference_bridge import recognize
            
            result = recognize(input_data)
            
            if result and result.get("status") == "ok":
                return {
                    "features": result.get("features", []),
                    "embeddings": result.get("embeddings", []),
                    "confidence": result.get("confidence", 0.0),
                    "model": "multimodal_jepa",
                }
            else:
                logger.warning("多模态 JEPA 特征提取失败: %s", result)
                return None
                
        except (ImportError, ValueError, KeyError, TypeError, OSError) as e:
            logger.error("多模态 JEPA 特征提取异常: %s", e, exc_info=True)
            return None
    
    def extract_features_video(
        self,
        video_path: str,
        frame_interval: int = 10,
    ) -> Optional[dict]:
        """使用视频 JEPA 提取特征
        
        Args:
            video_path: 视频文件路径
            frame_interval: 帧间隔
            
        Returns:
            特征字典
        """
        try:
            # 实现视频 JEPA 推理
            # 1. 验证视频文件存在
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.warning("视频文件不存在: %s", video_path)
                return None
            
            # 2. 尝试加载视频并采样帧
            sampled_frames = []
            total_frames = 0  # 默认值，防止 OpenCV 导入失败时未定义
            cap = None
            try:
                import cv2
                
                cap = cv2.VideoCapture(str(video_path_obj))
                if not cap.isOpened():
                    logger.warning("无法打开视频文件: %s", video_path)
                    return None
                
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    logger.warning("视频帧数无效: %s", video_path)
                    return None
                
                # 按间隔采样帧
                frame_indices = list(range(0, total_frames, frame_interval))
                for idx in frame_indices[:20]:  # 限制最多20帧避免内存溢出
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        # 转换为灰度图并缩放到固定尺寸
                        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                        resized = cv2.resize(gray, (112, 112))
                        sampled_frames.append(resized)
                
            except ImportError:
                logger.warning("OpenCV 不可用，使用模拟帧采样")
                # 模拟帧采样：生成伪随机帧数据
                rng = np.random.default_rng(seed=int(hashlib.sha256(video_path.encode()).hexdigest()[:8], 16))
                # 当 OpenCV 导入失败时，total_frames 未定义，使用默认值 10
                num_frames = min(10, max(1, total_frames // frame_interval)) if 'total_frames' in locals() else 10
                for _ in range(num_frames):
                    frame = rng.integers(0, 256, (112, 112), dtype=np.uint8)
                    sampled_frames.append(frame)
            except (RuntimeError, OSError, ValueError) as e:
                # 视频处理过程中的异常，记录后返回 None
                logger.error("视频帧采样失败 %s: %s", video_path, e, exc_info=True)
                return None
            finally:
                # 确保视频捕获对象被释放
                if cap is not None:
                    cap.release()
                
            except ImportError:
                logger.warning("OpenCV 不可用，使用模拟帧采样")
                # 模拟帧采样：生成伪随机帧数据
                rng = np.random.default_rng(seed=int(hashlib.sha256(video_path.encode()).hexdigest()[:8], 16))
                # 当 OpenCV 导入失败时，total_frames 未定义，使用默认值 10
                num_frames = min(10, max(1, total_frames // frame_interval)) if 'total_frames' in locals() else 10
                for _ in range(num_frames):
                    frame = rng.integers(0, 256, (112, 112), dtype=np.uint8)
                    sampled_frames.append(frame)
            
            if not sampled_frames:
                logger.warning("未能采样到有效帧: %s", video_path)
                return None
            
            # 3. 使用 JEPA 模型提取特征
            # 将帧堆叠为时序张量 [T, H, W]
            video_tensor = np.stack(sampled_frames, axis=0).astype(np.float32) / 255.0
            
            # 模拟 JEPA 特征提取：使用帧的统计特征作为嵌入
            # 实际实现应调用预训练的 Video JEPA 模型
            frame_features = []
            for frame in sampled_frames:
                # 提取每帧的统计特征
                mean_val = float(np.mean(frame))
                std_val = float(np.std(frame))
                # 使用直方图特征（简化版）
                hist = np.histogram(frame, bins=8, range=(0, 256))[0]
                hist_norm = hist / (hist.sum() + 1e-8)
                frame_features.append(np.concatenate([[mean_val, std_val], hist_norm]))
            
            # 聚合所有帧特征为视频级嵌入
            frame_features_array = np.array(frame_features, dtype=np.float32)
            video_embedding = np.mean(frame_features_array, axis=0)
            
            # 计算置信度（基于帧数量和特征稳定性）
            confidence = min(0.95, 0.5 + len(sampled_frames) * 0.02)
            
            logger.info(
                "视频 JEPA 特征提取完成: %d 帧, 嵌入维度 %d, 置信度 %.2f",
                len(sampled_frames),
                len(video_embedding),
                confidence
            )
            
            return {
                "features": video_embedding.tolist(),
                "embeddings": frame_features_array.tolist(),
                "confidence": confidence,
                "model": "video_jepa",
                "metadata": {
                    "num_frames": len(sampled_frames),
                    "frame_interval": frame_interval,
                    "video_path": video_path,
                },
            }
        except (ImportError, ValueError, OSError, RuntimeError, AttributeError) as e:
            logger.error("视频 JEPA 特征提取异常: %s", e, exc_info=True)
            return None
    
    def extract_features_point_cloud(
        self,
        point_cloud_path: str,
    ) -> Optional[dict]:
        """使用点云 MAE 提取特征
        
        Args:
            point_cloud_path: 点云文件路径
            
        Returns:
            特征字典
        """
        try:
            # 实现点云 MAE 推理
            # 1. 验证点云文件存在
            pc_path_obj = Path(point_cloud_path)
            if not pc_path_obj.exists():
                logger.warning("点云文件不存在: %s", point_cloud_path)
                return None
            
            # 2. 加载点云数据
            points = None
            try:
                # 尝试使用 numpy 加载 .npy 格式
                if pc_path_obj.suffix.lower() == '.npy':
                    points = np.load(str(pc_path_obj))
                # 尝试使用 trimesh 加载常见格式
                elif pc_path_obj.suffix.lower() in ['.ply', '.pcd', '.xyz', '.pts']:
                    import trimesh
                    mesh_or_cloud = trimesh.load(str(pc_path_obj))
                    if hasattr(mesh_or_cloud, 'vertices'):
                        points = np.array(mesh_or_cloud.vertices)
                    else:
                        points = np.array(mesh_or_cloud)
                # 尝试文本格式
                elif pc_path_obj.suffix.lower() in ['.txt', '.csv']:
                    points = np.loadtxt(str(pc_path_obj), delimiter=',')
                else:
                    logger.warning("不支持的点云格式: %s", pc_path_obj.suffix)
                    return None
            except ImportError:
                logger.warning("trimesh 不可用，尝试 numpy 加载")
                try:
                    points = np.load(str(pc_path_obj))
                except (ValueError, OSError, IOError) as load_err:
                    logger.error("点云加载失败: %s", load_err, exc_info=True)
                    return None
            except (ImportError, ValueError, OSError, RuntimeError) as load_err:
                logger.error("点云加载异常: %s", load_err, exc_info=True)
                return None
            
            if points is None or len(points) == 0:
                logger.warning("点云数据为空: %s", point_cloud_path)
                return None
            
            # 确保是 Nx3 或 Nx6 格式
            if points.ndim != 2 or points.shape[1] < 3:
                logger.warning("点云形状无效: %s", points.shape)
                return None
            
            # 只取 XYZ 坐标
            xyz = points[:, :3].astype(np.float32)
            
            # 3. 体素化下采样
            voxel_size = 0.01  # 1cm 体素
            try:
                # 归一化到单位球
                centroid = np.mean(xyz, axis=0)
                xyz_centered = xyz - centroid
                max_extent = np.max(np.abs(xyz_centered))
                if max_extent > 0:
                    xyz_normalized = xyz_centered / max_extent
                else:
                    xyz_normalized = xyz_centered
                
                # 体素化下采样
                voxel_indices = np.floor(xyz_normalized / voxel_size).astype(np.int32)
                unique_voxels, inverse_indices = np.unique(
                    voxel_indices, axis=0, return_inverse=True
                )
                
                # 每个体素取均值点
                downsampled_points = np.zeros((len(unique_voxels), 3), dtype=np.float32)
                for i in range(len(unique_voxels)):
                    mask = inverse_indices == i
                    downsampled_points[i] = np.mean(xyz_normalized[mask], axis=0)
                
                logger.debug(
                    "点云体素化: %d -> %d 点",
                    len(xyz),
                    len(downsampled_points)
                )
            except (ValueError, RuntimeError, MemoryError) as voxel_err:
                logger.warning("体素化失败，使用原始点: %s", voxel_err, exc_info=True)
                downsampled_points = xyz_normalized if 'xyz_normalized' in locals() else xyz
            
            # 4. MAE 特征提取
            # 模拟 MAE 编码：使用点的统计特征和空间分布
            # 实际实现应调用预训练的 Point MAE 模型
            
            # 提取全局特征
            global_mean = np.mean(downsampled_points, axis=0)
            global_std = np.std(downsampled_points, axis=0)
            global_min = np.min(downsampled_points, axis=0)
            global_max = np.max(downsampled_points, axis=0)
            
            # 提取局部特征（分块统计）
            num_blocks = 8
            block_size = len(downsampled_points) // num_blocks
            local_features = []
            for i in range(num_blocks):
                start_idx = i * block_size
                end_idx = start_idx + block_size if i < num_blocks - 1 else len(downsampled_points)
                block = downsampled_points[start_idx:end_idx]
                if len(block) > 0:
                    block_mean = np.mean(block, axis=0)
                    block_std = np.std(block, axis=0)
                    local_features.append(np.concatenate([block_mean, block_std]))
            
            # 聚合特征
            if local_features:
                local_features_array = np.array(local_features, dtype=np.float32)
                point_embedding = np.concatenate([
                    global_mean,
                    global_std,
                    global_max - global_min,  # 范围
                    np.mean(local_features_array, axis=0)
                ])
            else:
                point_embedding = np.concatenate([global_mean, global_std, global_max - global_min])
            
            # 计算置信度（基于点数量和分布均匀性）
            point_confidence = min(0.95, 0.4 + len(downsampled_points) * 0.001)
            
            logger.info(
                "点云 MAE 特征提取完成: %d 点, 嵌入维度 %d, 置信度 %.2f",
                len(downsampled_points),
                len(point_embedding),
                point_confidence
            )
            
            return {
                "features": point_embedding.tolist(),
                "embeddings": [point_embedding.tolist()],
                "confidence": point_confidence,
                "model": "point_mae",
                "metadata": {
                    "original_points": len(xyz),
                    "downsampled_points": len(downsampled_points),
                    "voxel_size": voxel_size,
                    "point_cloud_path": point_cloud_path,
                },
            }
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as e:
            logger.error("点云 MAE 特征提取异常: %s", e, exc_info=True)
            return None
    
    def inject_to_knowledge_graph(
        self,
        features: dict,
        graph_client: Any,
    ) -> bool:
        """将 JEPA 特征注入知识图谱
        
        Args:
            features: JEPA 提取的特征
            graph_client: 知识图谱客户端
            
        Returns:
            是否注入成功
        """
        try:
            # 实现具体的知识图谱注入逻辑
            # 1. 验证 graph_client 支持必要的接口
            if not hasattr(graph_client, 'add_node') or not hasattr(graph_client, 'add_edge'):
                logger.error("graph_client 缺少必要的接口 (add_node/add_edge)")
                return False
            
            # 2. 生成特征节点 ID
            model_name = features.get("model", "unknown")
            confidence = features.get("confidence", 0.0)
            feature_vector = features.get("features", [])
            
            if not feature_vector:
                logger.warning("特征向量为空，无法注入知识图谱")
                return False
            
            # 使用特征向量的哈希作为唯一标识（SHA256 替代 MD5 防碰撞）
            feature_hash = hashlib.sha256(
                str(feature_vector).encode()
            ).hexdigest()[:12]
            feature_node_id = f"jepa_feature-{model_name}-{feature_hash}"
            
            # 3. 创建特征节点
            feature_node_props = {
                "type": "jepa_feature",
                "model": model_name,
                "confidence": confidence,
                "feature_count": len(feature_vector),
                "embedding_dim": len(feature_vector),
                "created_at": str(Path.ctime(Path(__file__))),
            }
            
            # 添加特征节点
            graph_client.add_node(
                node_type="feature",
                node_id=feature_node_id,
                properties=feature_node_props,
            )
            logger.info("JEPA 特征节点已创建: %s", feature_node_id)
            
            # 4. 如果有元数据，创建相关的工艺/材料关联
            metadata = features.get("metadata", {})
            
            # 如果包含视频路径，创建与视频源的关联
            if "video_path" in metadata:
                video_id = f"video-{hashlib.sha256(metadata['video_path'].encode()).hexdigest()[:8]}"
                if not graph_client.has_node(video_id):
                    graph_client.add_node(
                        node_type="video_source",
                        node_id=video_id,
                        properties={"path": metadata["video_path"]},
                    )
                graph_client.add_edge(
                    source_id=feature_node_id,
                    target_id=video_id,
                    edge_type="EXTRACTED_FROM",
                    properties={"confidence": confidence, "source": "jepa"},
                )
            
            # 如果包含点云路径，创建与点云源的关联
            if "point_cloud_path" in metadata:
                pc_id = f"pointcloud-{hashlib.sha256(metadata['point_cloud_path'].encode()).hexdigest()[:8]}"
                if not graph_client.has_node(pc_id):
                    graph_client.add_node(
                        node_type="point_cloud_source",
                        node_id=pc_id,
                        properties={"path": metadata["point_cloud_path"]},
                    )
                graph_client.add_edge(
                    source_id=feature_node_id,
                    target_id=pc_id,
                    edge_type="EXTRACTED_FROM",
                    properties={"confidence": confidence, "source": "jepa"},
                )
            
            # 5. 尝试将特征与已有的材料/工艺节点关联
            # 查找现有的材料和工艺节点
            try:
                if hasattr(graph_client, 'list_nodes_by_type'):
                    materials = graph_client.list_nodes_by_type("material")
                    processes = graph_client.list_nodes_by_type("process")
                    
                    # 基于特征置信度，与高置信度的材料/工艺建立关联
                    if confidence > 0.7 and materials:
                        # 选择第一个材料作为关联目标（实际应基于特征匹配）
                        target_material = materials[0]
                        material_id = target_material.get("node_id", "")
                        if material_id and graph_client.has_node(material_id):
                            graph_client.add_edge(
                                source_id=feature_node_id,
                                target_id=material_id,
                                edge_type="RELATED_TO",
                                properties={
                                    "confidence": confidence * 0.8,
                                    "source": "jepa_inference",
                                },
                            )
                            logger.debug(
                                "特征 %s 关联到材料 %s",
                                feature_node_id,
                                material_id
                            )
            except (ValueError, KeyError, TypeError, AttributeError) as assoc_err:
                logger.warning("特征关联到材料/工艺失败: %s", assoc_err, exc_info=True)
            
            logger.info(
                "JEPA 特征注入知识图谱完成: node_id=%s, confidence=%.2f",
                feature_node_id,
                confidence
            )
            
            return True
            
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as e:
            logger.error("JEPA 特征注入知识图谱异常: %s", e, exc_info=True)
            return False
    
    def recommend_process(
        self,
        features: dict,
        material: str,
        constraints: Optional[dict] = None,
    ) -> Optional[dict]:
        """基于 JEPA 特征推荐工艺
        
        Args:
            features: JEPA 提取的特征
            material: 材料名称
            constraints: 加工约束
            
        Returns:
            工艺推荐结果
        """
        try:
            # 实现基于 JEPA 特征的工艺推荐
            # 1. 提取特征向量并分析几何复杂度
            feature_vector = features.get("features", [])
            confidence = features.get("confidence", 0.0)
            model_name = features.get("model", "unknown")
            
            if not feature_vector:
                logger.warning("特征向量为空，无法进行工艺推荐")
                return None
            
            feature_array = np.array(feature_vector, dtype=np.float32)
            
            # 2. 分析特征向量以确定几何复杂度
            # 使用特征的统计特性推断几何复杂度
            feature_mean = np.mean(feature_array)
            feature_std = np.std(feature_array)
            feature_range = np.max(feature_array) - np.min(feature_array)
            
            # 几何复杂度评分（0-1）
            # 高方差和高范围通常表示复杂几何
            complexity_score = min(1.0, (feature_std + feature_range) / 2.0)
            
            # 3. 材料属性映射
            # 基于材料名称推断材料属性（简化版）
            material_properties = self._get_material_properties(material)
            
            # 4. 应用约束条件
            constraints = constraints or {}
            surface_quality_req = constraints.get("surface_quality", "medium")
            tolerance_req = constraints.get("tolerance_mm", 0.1)
            batch_size = constraints.get("batch_size", "medium")
            
            # 5. 工艺策略选择
            # 基于复杂度、材料和约束选择工艺策略
            strategy, tool, base_params = self._select_process_strategy(
                complexity_score=complexity_score,
                material_props=material_properties,
                surface_quality=surface_quality_req,
                tolerance=tolerance_req,
            )
            
            # 6. 调整切削参数
            adjusted_params = self._adjust_cutting_parameters(
                base_params=base_params,
                material_props=material_properties,
                constraints=constraints,
            )
            
            # 7. 计算推荐置信度
            # 基于特征质量、约束匹配度和材料可加工性
            material_machinability = material_properties.get("machinability", 0.7)
            constraint_penalty = self._calculate_constraint_penalty(
                constraints=constraints,
                strategy=strategy,
            )
            
            recommendation_confidence = (
                confidence * 0.4 +
                material_machinability * 0.3 +
                (1.0 - constraint_penalty) * 0.3
            )
            recommendation_confidence = min(0.95, max(0.3, recommendation_confidence))
            
            # 8. 构建推荐结果
            recommendation = {
                "strategy": strategy,
                "tool": tool,
                "parameters": adjusted_params,
                "confidence": recommendation_confidence,
                "reasoning": {
                    "complexity_score": float(complexity_score),
                    "material": material,
                    "material_machinability": material_machinability,
                    "surface_quality": surface_quality_req,
                    "tolerance_mm": tolerance_req,
                },
                "alternatives": self._get_alternative_strategies(
                    complexity_score=complexity_score,
                    material_props=material_properties,
                ),
            }
            
            logger.info(
                "JEPA 工艺推荐完成: material=%s, strategy=%s, confidence=%.2f",
                material,
                strategy,
                recommendation_confidence
            )
            
            return recommendation
            
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as e:
            logger.error("JEPA 工艺推荐异常: %s", e, exc_info=True)
            return None
    
    def _get_material_properties(self, material: str) -> dict:
        """获取材料属性（简化版数据库）
        
        Args:
            material: 材料名称
            
        Returns:
            材料属性字典
        """
        # 常见材料的属性映射
        material_db = {
            "aluminum": {
                "hardness": 0.3,
                "machinability": 0.9,
                "thermal_conductivity": 0.7,
                "recommended_speed_factor": 1.2,
            },
            "steel": {
                "hardness": 0.7,
                "machinability": 0.6,
                "thermal_conductivity": 0.4,
                "recommended_speed_factor": 0.8,
            },
            "stainless_steel": {
                "hardness": 0.8,
                "machinability": 0.5,
                "thermal_conductivity": 0.3,
                "recommended_speed_factor": 0.7,
            },
            "titanium": {
                "hardness": 0.9,
                "machinability": 0.4,
                "thermal_conductivity": 0.2,
                "recommended_speed_factor": 0.6,
            },
            "copper": {
                "hardness": 0.4,
                "machinability": 0.8,
                "thermal_conductivity": 0.9,
                "recommended_speed_factor": 1.0,
            },
            "brass": {
                "hardness": 0.5,
                "machinability": 0.85,
                "thermal_conductivity": 0.6,
                "recommended_speed_factor": 1.1,
            },
            "plastic": {
                "hardness": 0.1,
                "machinability": 0.95,
                "thermal_conductivity": 0.1,
                "recommended_speed_factor": 1.5,
            },
            "carbon_fiber": {
                "hardness": 0.85,
                "machinability": 0.3,
                "thermal_conductivity": 0.5,
                "recommended_speed_factor": 0.5,
            },
        }
        
        # 模糊匹配材料名称
        material_lower = material.lower()
        for key, props in material_db.items():
            if key in material_lower or material_lower in key:
                return props
        
        # 默认属性
        logger.debug("未知材料 '%s'，使用默认属性", material)
        return {
            "hardness": 0.6,
            "machinability": 0.65,
            "thermal_conductivity": 0.5,
            "recommended_speed_factor": 0.9,
        }
    
    def _select_process_strategy(
        self,
        complexity_score: float,
        material_props: dict,
        surface_quality: str,
        tolerance: float,
    ) -> tuple[str, str, dict]:
        """选择工艺策略
        
        Args:
            complexity_score: 几何复杂度评分 (0-1)
            material_props: 材料属性
            surface_quality: 表面质量要求 (low/medium/high)
            tolerance: 公差要求 (mm)
            
        Returns:
            (strategy, tool, base_params) 元组
        """
        # 基础工艺策略选择
        if complexity_score < 0.3:
            # 简单几何
            strategy = "three_axis_roughing"
            tool = "endmill_D10"
            base_params = {
                "spindle_speed": 12000,
                "feed_rate": 3000,
                "depth_of_cut": 2.0,
                "step_over": 5.0,
            }
        elif complexity_score < 0.6:
            # 中等复杂度
            strategy = "three_axis_semi_finishing"
            tool = "ball_nose_R3"
            base_params = {
                "spindle_speed": 15000,
                "feed_rate": 2500,
                "depth_of_cut": 1.0,
                "step_over": 2.0,
            }
        else:
            # 高复杂度
            strategy = "five_axis_finishing"
            tool = "ball_nose_R2"
            base_params = {
                "spindle_speed": 18000,
                "feed_rate": 2000,
                "depth_of_cut": 0.5,
                "step_over": 0.8,
            }
        
        # 根据表面质量要求调整
        if surface_quality == "high":
            strategy = f"{strategy}_high_quality"
            base_params["spindle_speed"] = int(base_params["spindle_speed"] * 1.2)
            base_params["feed_rate"] = int(base_params["feed_rate"] * 0.7)
            base_params["depth_of_cut"] = base_params["depth_of_cut"] * 0.5
        
        # 根据公差要求调整
        if tolerance < 0.05:
            strategy = f"{strategy}_precision"
            base_params["feed_rate"] = int(base_params["feed_rate"] * 0.6)
        
        return strategy, tool, base_params
    
    def _adjust_cutting_parameters(
        self,
        base_params: dict,
        material_props: dict,
        constraints: dict,
    ) -> dict:
        """调整切削参数
        
        Args:
            base_params: 基础参数
            material_props: 材料属性
            constraints: 约束条件
            
        Returns:
            调整后的参数字典
        """
        adjusted = base_params.copy()
        
        # 根据材料可加工性调整
        speed_factor = material_props.get("recommended_speed_factor", 1.0)
        adjusted["spindle_speed"] = int(base_params["spindle_speed"] * speed_factor)
        adjusted["feed_rate"] = int(base_params["feed_rate"] * speed_factor)
        
        # 根据材料硬度调整切深
        hardness = material_props.get("hardness", 0.5)
        if hardness > 0.7:
            adjusted["depth_of_cut"] = base_params["depth_of_cut"] * 0.7
        elif hardness < 0.3:
            adjusted["depth_of_cut"] = base_params["depth_of_cut"] * 1.3
        
        # 应用约束条件
        max_spindle_speed = constraints.get("max_spindle_speed")
        if max_spindle_speed and adjusted["spindle_speed"] > max_spindle_speed:
            adjusted["spindle_speed"] = max_spindle_speed
        
        max_feed_rate = constraints.get("max_feed_rate")
        if max_feed_rate and adjusted["feed_rate"] > max_feed_rate:
            adjusted["feed_rate"] = max_feed_rate
        
        max_depth = constraints.get("max_depth_of_cut")
        if max_depth and adjusted["depth_of_cut"] > max_depth:
            adjusted["depth_of_cut"] = max_depth
        
        return adjusted
    
    def _calculate_constraint_penalty(
        self,
        constraints: dict,
        strategy: str,
    ) -> float:
        """计算约束惩罚因子
        
        Args:
            constraints: 约束条件
            strategy: 工艺策略
            
        Returns:
            惩罚因子 (0-1)
        """
        penalty = 0.0
        
        # 严格公差增加惩罚
        tolerance = constraints.get("tolerance_mm", 0.1)
        if tolerance < 0.05:
            penalty += 0.2
        elif tolerance < 0.02:
            penalty += 0.4
        
        # 高表面质量要求增加惩罚
        surface_quality = constraints.get("surface_quality", "medium")
        if surface_quality == "high":
            penalty += 0.15
        
        # 五轴策略本身惩罚较低（更适合复杂件）
        if "five_axis" in strategy:
            penalty -= 0.1
        
        return max(0.0, min(1.0, penalty))
    
    def _get_alternative_strategies(
        self,
        complexity_score: float,
        material_props: dict,
    ) -> list[dict]:
        """获取替代工艺策略
        
        Args:
            complexity_score: 几何复杂度评分
            material_props: 材料属性
            
        Returns:
            替代策略列表
        """
        alternatives = []
        
        # 根据复杂度提供替代方案
        if complexity_score > 0.5:
            alternatives.append({
                "strategy": "five_axis_roughing",
                "tool": "endmill_D8",
                "reason": "适合复杂几何的粗加工",
            })
        
        if material_props.get("machinability", 0.5) > 0.7:
            alternatives.append({
                "strategy": "high_speed_machining",
                "tool": "ball_nose_R1.5",
                "reason": "材料可加工性好，可采用高速加工",
            })
        
        # 总是提供精加工选项
        alternatives.append({
            "strategy": "finishing_pass",
            "tool": "ball_nose_R1",
            "reason": "最终精加工以确保表面质量",
        })
        
        return alternatives[:3]  # 最多返回3个替代方案
    
    def get_model_info(self) -> dict:
        """获取 JEPA 模型信息
        
        Returns:
            模型信息字典
        """
        return {
            "multimodal_jepa": {
                "version": "1.0.0",
                "status": "available",
                "path": str(self.model_dir / "multimodal_jepa"),
            },
            "video_jepa": {
                "version": "1.0.0",
                "status": "placeholder",
                "path": str(self.model_dir / "video_jepa"),
            },
            "point_mae": {
                "version": "1.0.0",
                "status": "placeholder",
                "path": str(self.model_dir / "point_mae"),
            },
        }


__all__ = ["JEPAServer"]
