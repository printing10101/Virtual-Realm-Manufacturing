"""
Kienzle 切削力模型

基于 Kienzle-Victor 公式计算主切削力：
F_c = k_c * h^mc * b

其中：
- k_c: 比切削力 (N/mm²)
- h: 切削厚度 (μm)，等于进给量 f * 1000
- mc: 切削力指数，通常取 0.25
- b: 切削宽度 (mm)，等于切深 a_p

材料相关的比切削力参数表：
| 材料     | k_c1.1 (N/mm²) | mc  |
|----------|----------------|-----|
| 45钢     | 1800           | 0.25|
| 304不锈钢| 2200           | 0.28|
| 40Cr     | 1950           | 0.26|
| 6061铝   | 700            | 0.22|
| TC4钛合金| 2500           | 0.30|
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialCuttingParams:
    """材料切削参数"""
    kc_base: float       # 比切削力基准值 (N/mm²)
    mc: float            # 切削力指数
    f_ref: float = 0.1   # 参考进给量 (mm/rev)


# 材料切削参数表
MATERIAL_PARAMS = {
    "45钢": MaterialCuttingParams(kc_base=1800.0, mc=0.25),
    "Q235": MaterialCuttingParams(kc_base=1600.0, mc=0.24),
    "40Cr": MaterialCuttingParams(kc_base=1950.0, mc=0.26),
    "20CrMnTi": MaterialCuttingParams(kc_base=1850.0, mc=0.25),
    "GCr15": MaterialCuttingParams(kc_base=2100.0, mc=0.27),
    "304不锈钢": MaterialCuttingParams(kc_base=2200.0, mc=0.28),
    "316不锈钢": MaterialCuttingParams(kc_base=2300.0, mc=0.29),
    "6061铝合金": MaterialCuttingParams(kc_base=700.0, mc=0.22),
    "7075铝合金": MaterialCuttingParams(kc_base=850.0, mc=0.23),
    "TC4": MaterialCuttingParams(kc_base=2500.0, mc=0.30),
}

# 默认参数（当材料不在表中时使用）
DEFAULT_PARAMS = MaterialCuttingParams(kc_base=2000.0, mc=0.25)


class KienzleModel:
    """
    Kienzle 切削力计算模型
    
    本模块为统一的切削力计算实现，已替换以下位置的原有代码：
    - validation_service.py: 已迁移使用 KienzleModel.calculate_specific_cutting_force
    - validation_engine.py: 已迁移为向后兼容的包装器，内部委托给本模块
    """

    @staticmethod
    def get_material_params(material: str) -> MaterialCuttingParams:
        """
        获取材料的切削参数
        
        Args:
            material: 材料名称
            
        Returns:
            材料切削参数，如果材料不在表中则返回默认参数
        """
        return MATERIAL_PARAMS.get(material, DEFAULT_PARAMS)

    @classmethod
    def calculate_specific_cutting_force(
        cls,
        f: float,
        material: str = "45钢",
        kc_base: float | None = None,
        mc: float | None = None,
    ) -> float:
        """
        计算比切削力 k_c (N/mm²)
        
        公式: k_c = kc_base * (f / f_ref) ^ (-mc)
        
        Args:
            f: 进给量 (mm/rev)
            material: 材料名称，用于查表获取参数
            kc_base: 比切削力基准值，如果提供则覆盖材料表中的值
            mc: 切削力指数，如果提供则覆盖材料表中的值
            
        Returns:
            比切削力 (N/mm²)
        """
        params = cls.get_material_params(material)
        kc = kc_base or params.kc_base
        mc_val = mc if mc is not None else params.mc
        
        if f <= 0:
            return 0.0
            
        return kc * ((f / params.f_ref) ** (-mc_val))

    @classmethod
    def calculate_cutting_force(
        cls,
        v_c: float,
        f: float,
        a_p: float,
        material: str = "45钢",
        kc_base: float | None = None,
        mc: float | None = None,
    ) -> dict[str, float]:
        """
        计算主切削力 F_c (N)
        
        公式: F_c = k_c * h * b
        其中 h = f * 1000 (μm), b = a_p (mm)
        
        Args:
            v_c: 切削速度 (m/min)
            f: 进给量 (mm/rev)
            a_p: 切深 (mm)
            material: 材料名称
            kc_base: 比切削力基准值，可选
            mc: 切削力指数，可选
            
        Returns:
            包含计算结果的字典：
            - cutting_force_N: 主切削力 (N)
            - specific_cutting_force_Nmm2: 比切削力 (N/mm²)
            - h_um: 切削厚度 (μm)
            - b_mm: 切削宽度 (mm)
        """
        kc = cls.calculate_specific_cutting_force(f, material, kc_base, mc)
        h = f * 1000  # 切削厚度 (μm)
        b = a_p        # 切削宽度 (mm)
        fc = kc * h * b / 1000  # 转换为 N
        
        return {
            "cutting_force_N": fc,
            "specific_cutting_force_Nmm2": kc,
            "h_um": h,
            "b_mm": b,
        }
