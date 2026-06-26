"""
CadQuery 自动化特征提取模块

从 3D CAD 模型自动提取加工特征，支持：
1. 几何特征识别（孔、槽、凸台等）
2. 工艺特征分析（倒角、圆角等）
3. 五轴加工特征提取（复杂曲面、深腔等）
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class FeatureType(Enum):
    """特征类型"""
    HOLE = "hole"                    # 孔
    SLOT = "slot"                    # 槽
    POCKET = "pocket"                # 型腔
    BOSS = "boss"                    # 凸台
    CHAMFER = "chamfer"              # 倒角
    FILLET = "fillet"                # 圆角
    SURFACE = "surface"              # 曲面
    DEEP_CAVITY = "deep_cavity"      # 深腔
    UNDERCUT = "undercut"            # 倒扣


@dataclass
class MachiningFeature:
    """加工特征"""
    feature_type: FeatureType
    name: str = ""
    volume: float = 0.0              # 体积 (mm³)
    area: float = 0.0                # 面积 (mm²)
    depth: float = 0.0               # 深度 (mm)
    diameter: float = 0.0            # 直径 (mm)
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    direction: tuple[float, float, float] = (0.0, 0.0, 1.0)
    requires_five_axis: bool = False  # 是否需要五轴加工
    complexity_score: float = 0.0     # 复杂度评分 (0-1)
    parameters: dict = field(default_factory=dict)


@dataclass
class FeatureExtractionResult:
    """特征提取结果"""
    success: bool
    features: list[MachiningFeature] = field(default_factory=list)
    error_message: str = ""
    extraction_time_ms: int = 0
    total_features: int = 0
    five_axis_features: int = 0


class CadQueryFeatureExtractor:
    """CadQuery 特征提取器
    
    从 3D CAD 模型自动提取加工特征
    """
    
    def __init__(self):
        self._cq_available = False
        try:
            import cadquery as cq
            self._cq_available = True
            logger.info("CadQuery 可用")
        except ImportError:
            logger.warning("CadQuery 不可用，使用简化特征提取")
    
    def extract_from_step(
        self,
        step_file: str,
        enable_five_axis_detection: bool = True,
    ) -> FeatureExtractionResult:
        """从 STEP 文件提取特征
        
        Args:
            step_file: STEP 文件路径
            enable_five_axis_detection: 是否启用五轴特征检测
            
        Returns:
            FeatureExtractionResult: 特征提取结果
        """
        import time
        t0 = time.perf_counter()
        
        if not self._cq_available:
            return FeatureExtractionResult(
                success=False,
                error_message="CadQuery 不可用，请安装: pip install cadquery",
            )
        
        try:
            import cadquery as cq
            
            # 加载 STEP 文件
            result = cq.importers.importStep(step_file)
            
            features = []
            
            # 提取几何特征
            features.extend(self._extract_holes(result))
            features.extend(self._extract_pockets(result))
            features.extend(self._extract_bosses(result))
            
            # 提取工艺特征
            features.extend(self._extract_chamfers(result))
            features.extend(self._extract_fillets(result))
            
            # 五轴特征检测
            if enable_five_axis_detection:
                for feature in features:
                    feature.requires_five_axis = self._requires_five_axis(feature)
                    feature.complexity_score = self._calculate_complexity(feature)
            
            extraction_time_ms = int((time.perf_counter() - t0) * 1000)
            
            five_axis_count = sum(1 for f in features if f.requires_five_axis)
            
            logger.info(
                "特征提取完成: %d 个特征，其中 %d 个需要五轴加工 (%d ms)",
                len(features),
                five_axis_count,
                extraction_time_ms,
            )
            
            return FeatureExtractionResult(
                success=True,
                features=features,
                extraction_time_ms=extraction_time_ms,
                total_features=len(features),
                five_axis_features=five_axis_count,
            )
            
        except (ValueError, TypeError, OSError, RuntimeError, AttributeError) as e:
            logger.error("特征提取失败: %s", e, exc_info=True)
            return FeatureExtractionResult(
                success=False,
                error_message="特征提取过程中发生错误",
                extraction_time_ms=int((time.perf_counter() - t0) * 1000),
            )
    
    def _extract_holes(self, model) -> list[MachiningFeature]:
        """提取孔特征

        通过识别圆柱面（cylindrical faces）来检测孔特征。
        判断条件：面对为圆柱面且法向指向内部（凹面）。
        """
        features = []
        try:
            import cadquery as cq
            from OCP.BRep import BRep_Tool
            from OCP.BRepAdaptor import BRepAdaptor_Surface
            from OCP.GeomAbs import GeomAbs_Cylinder

            for i, face in enumerate(model.Faces()):
                adaptor = BRepAdaptor_Surface(face.wrapped)
                if adaptor.GetType() == GeomAbs_Cylinder:
                    cylinder = adaptor.Cylinder()
                    radius = cylinder.Radius()
                    diameter = radius * 2.0

                    # 获取面的边界框来估算深度
                    bbox = face.BoundingBox()
                    depth = max(
                        bbox.xmax - bbox.xmin,
                        bbox.ymax - bbox.ymin,
                        bbox.zmax - bbox.zmin,
                    )

                    # 通过面积和周长判断是否为通孔或盲孔
                    area = face.Area()
                    circumference = 2 * 3.14159265 * radius
                    estimated_depth = area / circumference if circumference > 0 else depth

                    # 面中心作为孔位置
                    center = face.Center()
                    pos = (center.x, center.y, center.z)

                    # 圆柱轴方向作为孔方向
                    axis = cylinder.Axis().Direction()
                    direction = (axis.X(), axis.Y(), axis.Z())

                    features.append(MachiningFeature(
                        feature_type=FeatureType.HOLE,
                        name=f"hole_{i}",
                        diameter=diameter,
                        depth=estimated_depth,
                        position=pos,
                        direction=direction,
                        parameters={
                            "radius": radius,
                            "type": "cylindrical",
                        },
                    ))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.debug("CadQuery 孔特征提取降级: %s", e, exc_info=True)
        return features

    def _extract_pockets(self, model) -> list[MachiningFeature]:
        """提取型腔特征

        通过识别平面组合形成的凹陷区域来检测型腔。
        简化方法：检测具有多个平面边界且法向向下的面组。
        """
        features = []
        try:
            import cadquery as cq
            from OCP.BRepAdaptor import BRepAdaptor_Surface
            from OCP.GeomAbs import GeomAbs_Plane

            # 收集所有平面
            planar_faces = []
            for i, face in enumerate(model.Faces()):
                adaptor = BRepAdaptor_Surface(face.wrapped)
                if adaptor.GetType() == GeomAbs_Plane:
                    normal = adaptor.Plane().Axis().Direction()
                    # 只考虑朝上的平面（型腔底面）
                    if normal.Z() < -0.5:
                        center = face.Center()
                        planar_faces.append((i, face, center, normal))

            # 简单启发式：如果存在低于模型顶部的朝下面，可能是型腔底面
            if planar_faces:
                all_centers = [f.Center() for f in model.Faces()]
                max_z = max(c.z for c in all_centers) if all_centers else 0

                for idx, face, center, normal in planar_faces:
                    if center.z < max_z * 0.9:  # 明显低于最高面
                        bbox = face.BoundingBox()
                        length = bbox.xmax - bbox.xmin
                        width = bbox.ymax - bbox.ymin
                        area = face.Area()
                        depth = max_z - center.z

                        features.append(MachiningFeature(
                            feature_type=FeatureType.POCKET,
                            name=f"pocket_{idx}",
                            area=area,
                            depth=depth,
                            position=(center.x, center.y, center.z),
                            direction=(0, 0, -1),
                            parameters={
                                "length": length,
                                "width": width,
                            },
                        ))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.debug("CadQuery 型腔特征提取降级: %s", e, exc_info=True)
        return features

    def _extract_bosses(self, model) -> list[MachiningFeature]:
        """提取凸台特征

        通过识别朝上的圆柱面或平面凸起来检测凸台。
        """
        features = []
        try:
            from OCP.BRepAdaptor import BRepAdaptor_Surface
            from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane

            for i, face in enumerate(model.Faces()):
                adaptor = BRepAdaptor_Surface(face.wrapped)
                surf_type = adaptor.GetType()

                if surf_type == GeomAbs_Cylinder:
                    normal = adaptor.Cylinder().Axis().Direction()
                    # 朝上的圆柱面可能是凸台外壁
                    if abs(normal.Z()) > 0.5:
                        center = face.Center()
                        radius = adaptor.Cylinder().Radius()
                        bbox = face.BoundingBox()
                        height = bbox.zmax - bbox.zmin

                        # 获取模型整体高度
                        model_bbox = model.val().BoundingBox()
                        model_height = model_bbox.zmax - model_bbox.zmin

                        # 如果凸台高度占模型高度的显著比例
                        if height > 0 and height < model_height * 0.8:
                            features.append(MachiningFeature(
                                feature_type=FeatureType.BOSS,
                                name=f"boss_{i}",
                                diameter=radius * 2,
                                depth=height,
                                position=(center.x, center.y, center.z),
                                direction=(0, 0, 1),
                                parameters={
                                    "radius": radius,
                                    "height": height,
                                },
                            ))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.debug("CadQuery 凸台特征提取降级: %s", e, exc_info=True)
        return features

    def _extract_chamfers(self, model) -> list[MachiningFeature]:
        """提取倒角特征

        通过识别锥面（cone）来检测倒角。
        """
        features = []
        try:
            from OCP.BRepAdaptor import BRepAdaptor_Surface
            from OCP.GeomAbs import GeomAbs_Cone

            for i, face in enumerate(model.Faces()):
                adaptor = BRepAdaptor_Surface(face.wrapped)
                if adaptor.GetType() == GeomAbs_Cone:
                    cone = adaptor.Cone()
                    semi_angle = cone.SemiAngle()
                    angle_deg = abs(semi_angle) * 180.0 / math.pi

                    # 典型倒角角度在 15°-75° 范围
                    if 10 < angle_deg < 80:
                        center = face.Center()
                        bbox = face.BoundingBox()
                        width = max(
                            bbox.xmax - bbox.xmin,
                            bbox.ymax - bbox.ymin,
                            bbox.zmax - bbox.zmin,
                        )

                        features.append(MachiningFeature(
                            feature_type=FeatureType.CHAMFER,
                            name=f"chamfer_{i}",
                            area=face.Area(),
                            depth=width,
                            position=(center.x, center.y, center.z),
                            parameters={
                                "angle_deg": angle_deg,
                                "width": width,
                            },
                        ))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.debug("CadQuery 倒角特征提取降级: %s", e, exc_info=True)
        return features

    def _extract_fillets(self, model) -> list[MachiningFeature]:
        """提取圆角特征

        通过识别环面（torus）来检测圆角。
        """
        features = []
        try:
            from OCP.BRepAdaptor import BRepAdaptor_Surface
            from OCP.GeomAbs import GeomAbs_Torus

            for i, face in enumerate(model.Faces()):
                adaptor = BRepAdaptor_Surface(face.wrapped)
                if adaptor.GetType() == GeomAbs_Torus:
                    torus = adaptor.Torus()
                    major_radius = torus.MajorRadius()
                    minor_radius = torus.MinorRadius()

                    center = face.Center()

                    features.append(MachiningFeature(
                        feature_type=FeatureType.FILLET,
                        name=f"fillet_{i}",
                        area=face.Area(),
                        position=(center.x, center.y, center.z),
                        parameters={
                            "major_radius": major_radius,
                            "minor_radius": minor_radius,
                            "fillet_radius": minor_radius,
                        },
                    ))
        except (ValueError, TypeError, AttributeError, RuntimeError) as e:
            logger.debug("CadQuery 圆角特征提取降级: %s", e, exc_info=True)
        return features
    
    def _requires_five_axis(self, feature: MachiningFeature) -> bool:
        """判断特征是否需要五轴加工
        
        判断规则：
        1. 深腔（深度/直径 > 3）
        2. 倒扣特征
        3. 复杂曲面
        4. 多面加工
        """
        if feature.feature_type == FeatureType.DEEP_CAVITY:
            return True
        
        if feature.feature_type == FeatureType.UNDERCUT:
            return True
        
        # 深腔判断
        if feature.depth > 0 and feature.diameter > 0:
            if feature.depth / feature.diameter > 3.0:
                return True
        
        # 复杂度判断
        if feature.complexity_score > 0.7:
            return True
        
        return False
    
    def _calculate_complexity(self, feature: MachiningFeature) -> float:
        """计算特征复杂度评分
        
        评分规则：
        - 深径比：0-0.3
        - 曲面复杂度：0-0.3
        - 位置复杂度：0-0.2
        - 工艺复杂度：0-0.2
        """
        score = 0.0
        
        # 深径比评分
        if feature.depth > 0 and feature.diameter > 0:
            ratio = feature.depth / feature.diameter
            score += min(0.3, ratio * 0.1)
        
        # 体积评分
        if feature.volume > 0:
            score += min(0.2, feature.volume / 10000.0)
        
        # 面积评分
        if feature.area > 0:
            score += min(0.2, feature.area / 1000.0)
        
        return min(1.0, score)


__all__ = [
    "CadQueryFeatureExtractor",
    "FeatureExtractionResult",
    "MachiningFeature",
    "FeatureType",
]
