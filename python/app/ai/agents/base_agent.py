"""基础 Agent 类和上下文定义"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class AgentContext:
    """Agent 执行上下文"""
    
    current_stage: str = ""
    stage_status: str = "pending"
    extracted_params: Dict[str, Any] = field(default_factory=dict)
    cutting_parameters: Optional[Dict[str, Any]] = None
    verification_result: Optional[Dict[str, Any]] = None
    
    def set_param(self, key: str, value: Any) -> None:
        """设置参数"""
        self.extracted_params[key] = value
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """获取参数"""
        return self.extracted_params.get(key, default)


class BaseAgent(ABC):
    """基础 Agent 类"""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentContext:
        """执行 Agent 逻辑"""
        pass
    
    async def _call_llm_via_router(
        self,
        messages: list,
        max_tokens: int = 512,
        temperature: float = 0.7,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """调用 LLM 的辅助方法（简化实现）"""
        # 这里应该调用实际的 LLM 服务
        # 简化实现返回模拟响应
        return {
            "content": '{"cutting_speed": 150, "feed_rate": 0.2, "depth_of_cut": 2.0, "spindle_speed": 800}'
        }
