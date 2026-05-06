"""
表面粗糙度模型

基于理论公式计算车削加工的表面粗糙度：
Ra = f² / (8 * rε) * 1000

其中：
- f: 进给量 (mm/rev)
- rε: 刀尖圆弧半径 (mm)，通常取 0.8mm
- Ra: 表面粗糙度 (μm)
"""


class SurfaceRoughnessModel:
    """
    表面粗糙度计算模型
    
    统一替换以下位置的重复实现：
    - validation_service.py:L154-155
    - validation_engine.py:L123-126
    """

    @staticmethod
    def calculate_ra(
        f: float,
        nose_radius: float = 0.8,
    ) -> float:
        """
        计算理论表面粗糙度 Ra (μm)
        
        公式: Ra = f² / (8 * rε) * 1000
        
        Args:
            f: 进给量 (mm/rev)
            nose_radius: 刀尖圆弧半径 (mm)，默认0.8mm
            
        Returns:
            表面粗糙度 Ra (μm)，如果 nose_radius <= 0 则返回 0.0
        """
        if nose_radius <= 0:
            return 0.0
        return (f ** 2) / (8 * nose_radius) * 1000

    @staticmethod
    def calculate_max_feed(
        ra_limit: float,
        nose_radius: float = 0.8,
    ) -> float:
        """
        计算满足表面粗糙度要求的最大进给量
        
        公式: f = sqrt(Ra * 8 * rε / 1000)
        
        Args:
            ra_limit: 目标表面粗糙度 (μm)
            nose_radius: 刀尖圆弧半径 (mm)
            
        Returns:
            最大进给量 (mm/rev)
        """
        if ra_limit <= 0 or nose_radius <= 0:
            return 0.0
        return (ra_limit * 8 * nose_radius / 1000) ** 0.5
