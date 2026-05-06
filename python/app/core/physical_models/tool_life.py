"""
Taylor 刀具寿命模型

基于 Taylor 公式计算刀具寿命：
V_c * T^n = C

其中：
- V_c: 切削速度 (m/min)
- T: 刀具寿命 (min)
- n: Taylor指数，通常取 0.25
- C: 切削常数，取决于刀具材料和工件材料

转换公式: T = (C / V_c) ^ (1/n)

材料-刀具组合的Taylor参数表：
| 工件材料   | 刀具材料      | C    | n    |
|------------|--------------|------|------|
| 45钢       | 硬质合金      | 350  | 0.25 |
| 304不锈钢  | 硬质合金      | 180  | 0.22 |
| 6061铝     | 高速钢        | 600  | 0.30 |
| TC4钛合金  | 硬质合金      | 120  | 0.20 |
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TaylorParams:
    """Taylor模型参数"""
    C: float    # 切削常数
    n: float    # Taylor指数


# Taylor参数表
TAYLOR_PARAMS = {
    "45钢": TaylorParams(C=350.0, n=0.25),
    "Q235": TaylorParams(C=380.0, n=0.26),
    "40Cr": TaylorParams(C=320.0, n=0.24),
    "304不锈钢": TaylorParams(C=180.0, n=0.22),
    "316不锈钢": TaylorParams(C=170.0, n=0.21),
    "6061铝合金": TaylorParams(C=600.0, n=0.30),
    "TC4": TaylorParams(C=120.0, n=0.20),
}

# 默认参数
DEFAULT_PARAMS = TaylorParams(C=350.0, n=0.25)


class TaylorModel:
    """
    Taylor 刀具寿命计算模型
    
    统一替换以下位置的重复实现：
    - validation_service.py:L150-152
    - validation_engine.py:L116-121
    """

    @staticmethod
    def get_params(material: str) -> TaylorParams:
        """
        获取材料的Taylor参数
        
        Args:
            material: 材料名称
            
        Returns:
            Taylor参数，如果材料不在表中则返回默认参数
        """
        return TAYLOR_PARAMS.get(material, DEFAULT_PARAMS)

    @classmethod
    def calculate_tool_life(
        cls,
        v_c: float,
        material: str = "45钢",
        n: float | None = None,
        c: float | None = None,
    ) -> float:
        """
        计算刀具寿命 (min)
        
        公式: T = (C / V_c) ^ (1/n)
        
        Args:
            v_c: 切削速度 (m/min)
            material: 材料名称
            n: Taylor指数，可选，如果提供则覆盖默认值
            c: 切削常数，可选，如果提供则覆盖默认值
            
        Returns:
            刀具寿命 (min)，如果v_c <= 0则返回0.0
        """
        if v_c <= 0:
            return 0.0
            
        params = cls.get_params(material)
        n_val = n if n is not None else params.n
        c_val = c if c is not None else params.C
        
        return (c_val / v_c) ** (1 / n_val)

    @classmethod
    def calculate_max_speed(
        cls,
        target_life: float,
        material: str = "45钢",
        n: float | None = None,
        c: float | None = None,
    ) -> float:
        """
        计算目标刀具寿命下的最大切削速度
        
        公式: V_c = C / T^n
        
        Args:
            target_life: 目标刀具寿命 (min)
            material: 材料名称
            n: Taylor指数，可选
            c: 切削常数，可选
            
        Returns:
            最大切削速度 (m/min)
        """
        if target_life <= 0:
            return 0.0
            
        params = cls.get_params(material)
        n_val = n if n is not None else params.n
        c_val = c if c is not None else params.C
        
        return c_val / (target_life ** n_val)
