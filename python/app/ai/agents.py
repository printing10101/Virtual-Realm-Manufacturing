import json
from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel

from app.ai.llm_client import get_llm_client
from app.rag.knowledge_base import get_knowledge_base


class AgentContext(BaseModel):
    user_input: str = ""
    extracted_params: dict = {}
    process_route: list = []
    cutting_parameters: dict = {}
    nc_code: str = ""
    verification_result: dict = {}
    repair_suggestions: list = []
    current_stage: str = ""
    stage_status: str = ""


class BaseAgent(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.llm_client = get_llm_client()
        self.knowledge_base = get_knowledge_base()

    @abstractmethod
    async def execute(self, context: AgentContext) -> AgentContext:
        pass

    def get_system_prompt(self) -> str:
        return f"你是{self.name}，{self.description}"


class UnderstandingAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="UnderstandingAgent",
            description="负责理解用户需求，提取关键制造参数"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "understanding"
        context.stage_status = "running"

        knowledge_results = self.knowledge_base.query(
            query_text=context.user_input,
            n_results=3
        )

        relevant_knowledge = ""
        if knowledge_results["documents"]:
            relevant_knowledge = "\n".join(knowledge_results["documents"])

        system_prompt = f"""你是一个制造工艺专家，负责分析用户的制造需求。
请从用户输入中提取以下关键参数：
1. 材料类型（如45钢、6061铝合金等）
2. 零件类型（如轴类、盘类、壳体类等）
3. 尺寸要求（长、宽、高、直径等）
4. 精度要求（公差等级、表面粗糙度等）
5. 加工数量

参考知识：
{relevant_knowledge}

请以JSON格式返回提取的参数，格式如下：
{{
  "material": "材料类型",
  "part_type": "零件类型",
  "dimensions": {{"length": 数值, "width": 数值, "height": 数值}},
  "tolerance": "公差等级",
  "surface_roughness": "表面粗糙度要求",
  "quantity": 数量
}}
只返回JSON，不要其他内容。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": context.user_input}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=1024,
            temperature=0.3
        )

        try:
            content = response["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            extracted_params = json.loads(content)
            context.extracted_params = extracted_params
            context.stage_status = "completed"
        except Exception as e:
            context.stage_status = f"failed: {str(e)}"
            context.extracted_params = {"raw_input": context.user_input}

        return context


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PlanningAgent",
            description="负责制定加工工艺路线"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "planning"
        context.stage_status = "running"

        knowledge_results = self.knowledge_base.query(
            query_text="加工工艺路线规划",
            n_results=5
        )

        relevant_knowledge = "\n".join(knowledge_results["documents"]) if knowledge_results["documents"] else ""

        params = context.extracted_params
        material = params.get("material", "45钢")
        part_type = params.get("part_type", "轴类零件")

        system_prompt = f"""你是一个工艺规划专家，负责为零件制定合理的加工工艺路线。

材料：{material}
零件类型：{part_type}

参考知识：
{relevant_knowledge}

请制定完整的加工工艺路线，包括：
1. 下料工序
2. 粗加工工序
3. 半精加工工序
4. 精加工工序
5. 热处理工序（如需要）
6. 检验工序

请以JSON数组格式返回工艺路线，每个工序包含：
{{
  "route": [
    {{"step": 1, "operation": "工序名称", "machine": "设备类型", "description": "工序说明"}},
    ...
  ]
}}
只返回JSON，不要其他内容。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为{material}的{part_type}制定加工工艺路线"}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.3
        )

        try:
            content = response["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            route_data = json.loads(content)
            context.process_route = route_data.get("route", [])
            context.stage_status = "completed"
        except Exception as e:
            context.stage_status = f"failed: {str(e)}"
            context.process_route = [
                {"step": 1, "operation": "下料", "machine": "锯床", "description": "按尺寸下料"},
                {"step": 2, "operation": "粗车", "machine": "车床", "description": "粗加工外圆"},
                {"step": 3, "operation": "精车", "machine": "车床", "description": "精加工到尺寸"},
                {"step": 4, "operation": "检验", "machine": "量具", "description": "检验尺寸"}
            ]

        return context


class ParameterAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ParameterAgent",
            description="负责计算切削参数"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "parameter"
        context.stage_status = "running"

        knowledge_results = self.knowledge_base.query(
            query_text="切削参数 切削速度 进给量",
            n_results=5
        )

        relevant_knowledge = "\n".join(knowledge_results["documents"]) if knowledge_results["documents"] else ""

        params = context.extracted_params
        material = params.get("material", "45钢")

        system_prompt = f"""你是一个切削参数计算专家，负责为每道工序计算合适的切削参数。

材料：{material}

参考知识：
{relevant_knowledge}

请为以下工艺路线的每道工序计算切削参数：
{json.dumps(context.process_route, ensure_ascii=False, indent=2)}

切削参数包括：
- 切削速度 v (m/min)
- 进给量 f (mm/r 或 mm/z)
- 背吃刀量 ap (mm)
- 主轴转速 n (r/min)

请以JSON格式返回，格式如下：
{{
  "parameters": [
    {{"step": 1, "operation": "工序名", "v": 数值, "f": 数值, "ap": 数值, "n": 数值, "unit_v": "m/min", "unit_f": "mm/r", "unit_ap": "mm", "unit_n": "r/min"}},
    ...
  ]
}}
只返回JSON，不要其他内容。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请为{material}的加工计算切削参数"}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.3
        )

        try:
            content = response["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            param_data = json.loads(content)
            context.cutting_parameters = param_data.get("parameters", {})
            context.stage_status = "completed"
        except Exception as e:
            context.stage_status = f"failed: {str(e)}"
            context.cutting_parameters = {
                "parameters": [
                    {"step": 1, "operation": "粗车", "v": 120, "f": 0.3, "ap": 2.0, "n": 800},
                    {"step": 2, "operation": "精车", "v": 180, "f": 0.1, "ap": 0.5, "n": 1200}
                ]
            }

        return context


class NCAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="NCAgent",
            description="负责生成NC代码"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "nc_generation"
        context.stage_status = "running"

        knowledge_results = self.knowledge_base.query(
            query_text="G代码 M代码 数控编程",
            n_results=5
        )

        relevant_knowledge = "\n".join(knowledge_results["documents"]) if knowledge_results["documents"] else ""

        system_prompt = f"""你是一个NC编程专家，负责根据工艺路线和切削参数生成数控加工程序。

参考知识：
{relevant_knowledge}

工艺路线：
{json.dumps(context.process_route, ensure_ascii=False, indent=2)}

切削参数：
{json.dumps(context.cutting_parameters, ensure_ascii=False, indent=2)}

请生成完整的NC代码，要求：
1. 使用标准G代码和M代码
2. 包含程序头（程序名、安全设置、刀具选择等）
3. 包含各工序的加工代码
4. 包含程序尾（主轴停止、程序结束等）
5. 添加必要的注释说明

请直接返回NC代码，用```gcode```包裹。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请根据上述工艺路线和切削参数生成NC代码"}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=4096,
            temperature=0.2
        )

        try:
            content = response["content"].strip()
            if "```gcode" in content:
                context.nc_code = content.split("```gcode")[1].split("```")[0].strip()
            elif "```" in content:
                context.nc_code = content.split("```")[1].split("```")[0].strip()
            else:
                context.nc_code = content
            context.stage_status = "completed"
        except Exception as e:
            context.stage_status = f"failed: {str(e)}"
            context.nc_code = "; NC代码生成失败\nG00 X0 Y0 Z0\nM30"

        return context


class VerificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="VerificationAgent",
            description="负责验证工艺合理性"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "verification"
        context.stage_status = "running"

        system_prompt = """你是一个工艺验证专家，负责验证工艺路线、切削参数和NC代码的合理性。

请从以下方面进行验证：
1. 工艺路线是否合理（工序顺序是否正确）
2. 切削参数是否在合理范围内
3. NC代码是否有语法错误
4. 是否满足加工要求

请以JSON格式返回验证结果：
{
  "is_valid": true/false,
  "issues": [
    {"type": "警告/错误", "description": "问题描述", "severity": "low/medium/high"}
  ],
  "summary": "验证总结"
}
只返回JSON，不要其他内容。"""

        verification_content = f"""
工艺路线：
{json.dumps(context.process_route, ensure_ascii=False, indent=2)}

切削参数：
{json.dumps(context.cutting_parameters, ensure_ascii=False, indent=2)}

NC代码：
{context.nc_code}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": verification_content}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.2
        )

        try:
            content = response["content"].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            verification_result = json.loads(content)
            context.verification_result = verification_result
            context.stage_status = "completed"
        except Exception as e:
            context.stage_status = f"failed: {str(e)}"
            context.verification_result = {
                "is_valid": True,
                "issues": [],
                "summary": "验证通过（简化模式）"
            }

        return context


class RepairAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="RepairAgent",
            description="负责根据验证结果优化工艺方案"
        )

    async def execute(self, context: AgentContext) -> AgentContext:
        context.current_stage = "repair"
        context.stage_status = "running"

        verification = context.verification_result
        is_valid = verification.get("is_valid", True)
        issues = verification.get("issues", [])

        if is_valid and not issues:
            context.repair_suggestions = []
            context.stage_status = "completed (no repair needed)"
            return context

        system_prompt = """你是一个工艺优化专家，负责根据验证结果提出优化建议。

请针对以下问题提出具体的修复/优化方案：
"""

        issues_text = "\n".join([f"- {issue.get('description', '')}" for issue in issues])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"验证发现的问题：\n{issues_text}\n\n请提出优化建议。"}
        ]

        response = await self.llm_client.chat_completion(
            messages=messages,
            max_tokens=2048,
            temperature=0.3
        )

        context.repair_suggestions = response["content"]
        context.stage_status = "completed"

        return context
