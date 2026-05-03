import json
import re
from typing import Dict, Any, List, Optional
from app.models.experience import ProcessExperience, ExperienceStatus
from app.services.ai_service import AIService


EXTRACT_FROM_FEEDBACK_PROMPT = """你是一个经验丰富的机械加工工艺专家。请分析以下加工反馈，提取经验规则。

## 加工任务结果
{task_result}

## 用户反馈
{user_feedback}

请以 JSON 格式返回分析结果，格式如下：
```json
{{
  "status": "success" 或 "failure" 或 "partial",
  "failure_reason": "如果失败，失败原因是什么（成功则为空）",
  "correction_suggestion": "如果失败或部分成功，如何改进（成功则为空）",
  "extracted_rules": [
    "规则1，例如：当材料硬度>200HB时，切削速度上限下调20%",
    "规则2"
  ],
  "similarity_key": "用于向量检索的语义描述，格式：材料+硬度+刀具+工序+关键参数特征"
}}
```

只返回 JSON，不要包含其他文字说明。
"""

EXTRACT_FROM_VALIDATION_PROMPT = """你是一个经验丰富的机械加工工艺专家。请分析以下在线验证结果，提取经验规则。

## 验证结果
{validation_result}

请以 JSON 格式返回分析结果，格式如下：
```json
{{
  "status": "success"（所有指标达标）或 "partial"（部分指标超标）或 "failure"（多项指标严重超标）,
  "exceeded_metrics": [
    {{
      "metric": "指标名称",
      "predicted": "预测值",
      "actual": "实际值",
      "error_percent": "误差百分比"
    }}
  ],
  "extracted_rules": [
    "规则1，例如：该材料使用此刀具时，进给量不宜超过0.25mm/rev",
    "规则2"
  ],
  "similarity_key": "用于向量检索的语义描述，格式：材料+刀具+工序+关键参数特征"
}}
```

只返回 JSON，不要包含其他文字说明。
"""


class ExperienceExtractor:
    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def extract_from_feedback(
        self,
        task_result: Dict[str, Any],
        user_feedback: str,
        task_id: str = "experience_extraction"
    ) -> ProcessExperience:
        prompt = EXTRACT_FROM_FEEDBACK_PROMPT.format(
            task_result=json.dumps(task_result, ensure_ascii=False, indent=2),
            user_feedback=user_feedback
        )

        system_prompt = "你是机械加工工艺专家，擅长从加工结果中提取经验规则。"

        response = await self.ai_service.call_llm(
            task_id=task_id,
            agent_name="experience_extractor",
            prompt=prompt,
            system_prompt=system_prompt
        )

        extraction = self._parse_json_response(response.get("content", ""))

        experience = ProcessExperience(
            status=ExperienceStatus(extraction.get("status", "partial")),
            scenario=task_result.get("scenario", ""),
            material=task_result.get("material", ""),
            tool=task_result.get("tool", ""),
            operation=task_result.get("operation", ""),
            params=task_result.get("params", {}),
            results=task_result.get("results", {}),
            feedback=user_feedback,
            extracted_rules=extraction.get("extracted_rules", []),
            similarity_key=extraction.get("similarity_key", "")
        )

        return experience

    async def extract_from_validation(
        self,
        validation_result: Dict[str, Any],
        task_id: str = "experience_extraction_validation"
    ) -> ProcessExperience:
        prompt = EXTRACT_FROM_VALIDATION_PROMPT.format(
            validation_result=json.dumps(validation_result, ensure_ascii=False, indent=2)
        )

        system_prompt = "你是机械加工工艺专家，擅长从验证结果中提取经验规则。"

        response = await self.ai_service.call_llm(
            task_id=task_id,
            agent_name="experience_extractor",
            prompt=prompt,
            system_prompt=system_prompt
        )

        extraction = self._parse_json_response(response.get("content", ""))

        experience = ProcessExperience(
            status=ExperienceStatus(extraction.get("status", "partial")),
            scenario=validation_result.get("scenario", ""),
            material=validation_result.get("material", ""),
            tool=validation_result.get("tool", ""),
            operation=validation_result.get("operation", ""),
            params=validation_result.get("params", {}),
            results=validation_result.get("results", {}),
            feedback="在线验证自动提取",
            extracted_rules=extraction.get("extracted_rules", []),
            similarity_key=extraction.get("similarity_key", "")
        )

        return experience

    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        content = content.strip()

        json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)

        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return {
            "status": "partial",
            "failure_reason": "",
            "correction_suggestion": "",
            "extracted_rules": [],
            "similarity_key": ""
        }
