import json
import re
from typing import Any

from app.core.scenario_manager import scenario_manager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.models.hypothesis import ProcessHypothesis
from app.services.ai_service import AIService
from app.services.experience_store import ExperienceStore


class HypothesisGenerator:
    def __init__(self, ai_service: AIService, workflow_logger: AIWorkflowLogger, experience_store: ExperienceStore | None = None):
        self.ai_service = ai_service
        self.logger = workflow_logger
        self.experience_store = experience_store
        self._knowledge_cache: list[dict[str, Any]] = []

    async def generate_initial_hypothesis(
        self,
        task_id: str,
        requirements: dict[str, Any],
        material_info: dict[str, Any],
        tool_info: dict[str, Any],
        history_reference: list[dict[str, Any]] | None = None,
        scenario_id: str = "base"
    ) -> ProcessHypothesis:
        history_text = self._format_history_reference(history_reference or [])

        if self.experience_store:
            material = material_info.get("name", "")
            tool = tool_info.get("name", "")
            operation = requirements.get("operation", "")
            params = requirements.get("params", {})

            similar = self.experience_store.query_similar(
                material=material,
                tool=tool,
                operation=operation,
                params=params,
                top_k=3
            )

            success_exp_text = self._format_similar_experiences(similar.get("success_experiences", []), is_success=True)
            failure_exp_text = self._format_similar_experiences(similar.get("failure_experiences", []), is_success=False)
            history_text += success_exp_text + failure_exp_text

        try:
            prompt_template = scenario_manager.get_prompts(scenario_id, "initial_hypothesis")
        except Exception:
            prompt_template = scenario_manager.get_prompts("base", "initial_hypothesis")

        prompt = prompt_template.format(
            requirements=json.dumps(requirements, ensure_ascii=False, indent=2),
            material_info=json.dumps(material_info, ensure_ascii=False, indent=2),
            tool_info=json.dumps(tool_info, ensure_ascii=False, indent=2),
            history_reference=history_text
        )

        system_prompt = "你是机械加工工艺专家，擅长根据工件材料和加工要求生成合理的工艺假设。"

        with self.logger.log_step(
            task_id, "hypothesis_generator", StepType.LLM_CALL,
            input_data={"prompt_type": "initial_hypothesis", "requirements": requirements}
        ) as log_entry:
            response = await self.ai_service.call_llm(
                task_id=task_id,
                agent_name="hypothesis_generator",
                prompt=prompt,
                system_prompt=system_prompt
            )
            log_entry.output = {"response_length": len(response.get("content", ""))}

        hypothesis_data = self._parse_json_response(response.get("content", ""))

        hypothesis = ProcessHypothesis(
            content=hypothesis_data.get("content", ""),
            reason=hypothesis_data.get("reason", ""),
            expected_outcomes=hypothesis_data.get("expected_outcomes", {}),
            confidence=float(hypothesis_data.get("confidence", 0.5)),
            source="llm_generated"
        )

        return hypothesis

    async def generate_correction_hypothesis(
        self,
        task_id: str,
        failed_hypothesis: ProcessHypothesis,
        validation_feedback: dict[str, Any],
        trace_chain: list[dict[str, Any]] | None = None,
        scenario_id: str = "base"
    ) -> ProcessHypothesis:
        failure_reason = validation_feedback.get("failure_reason", "未知原因")
        unmet_constraints = validation_feedback.get("unmet_constraints", [])
        trace_chain_text = self._format_trace_chain(trace_chain or [])

        try:
            prompt_template = scenario_manager.get_prompts(scenario_id, "correction_hypothesis")
        except Exception:
            prompt_template = scenario_manager.get_prompts("base", "correction_hypothesis")

        prompt = prompt_template.format(
            failed_hypothesis=failed_hypothesis.content,
            failure_reason=failure_reason,
            validation_feedback=json.dumps(validation_feedback, ensure_ascii=False, indent=2),
            unmet_constraints=json.dumps(unmet_constraints, ensure_ascii=False, indent=2),
            trace_chain=trace_chain_text
        )

        system_prompt = "你是机械加工工艺专家，擅长分析加工失败原因并修正工艺参数。"

        with self.logger.log_step(
            task_id, "hypothesis_generator", StepType.LLM_CALL,
            input_data={"prompt_type": "correction_hypothesis", "failed_hypothesis_id": failed_hypothesis.hypothesis_id}
        ) as log_entry:
            response = await self.ai_service.call_llm(
                task_id=task_id,
                agent_name="hypothesis_generator",
                prompt=prompt,
                system_prompt=system_prompt
            )
            log_entry.output = {"response_length": len(response.get("content", ""))}

        hypothesis_data = self._parse_json_response(response.get("content", ""))

        hypothesis = ProcessHypothesis(
            content=hypothesis_data.get("content", ""),
            reason=hypothesis_data.get("reason", ""),
            expected_outcomes=hypothesis_data.get("expected_outcomes", {}),
            confidence=float(hypothesis_data.get("confidence", 0.5)),
            source="user_feedback",
            based_on_hypothesis_id=failed_hypothesis.hypothesis_id
        )

        return hypothesis

    def _parse_json_response(self, content: str) -> dict[str, Any]:
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

        confidence = self._calculate_fallback_confidence(content)
        return {
            "content": content[:200],
            "reason": "基于现有信息生成的假设",
            "expected_outcomes": {},
            "confidence": confidence
        }

    def _calculate_fallback_confidence(self, content: str) -> float:
        if not content or len(content) < 10:
            return 0.2
        has_numbers = bool(re.search(r'\d+\.?\d*', content))
        has_structured = any(kw in content for kw in ["切削", "速度", "进给", "刀具", "表面"])
        base = 0.3
        if has_numbers:
            base += 0.1
        if has_structured:
            base += 0.1
        return min(base, 0.5)

    def _format_history_reference(self, history: list[dict[str, Any]]) -> str:
        if not history:
            return "无历史经验参考"

        lines = []
        for i, item in enumerate(history, 1):
            lines.append(f"{i}. 工况：{item.get('material', '')} {item.get('part_type', '')}")
            lines.append(f"   参数：切削速度 {item.get('cutting_speed', '')} m/min, "
                        f"进给量 {item.get('feed_rate', '')} mm/rev")
            lines.append(f"   效果：{item.get('result_summary', '')}")

        return "\n".join(lines)

    def _format_trace_chain(self, trace_chain: list[dict[str, Any]]) -> str:
        if not trace_chain:
            return "无历史演化记录"

        lines = []
        for i, item in enumerate(trace_chain, 1):
            lines.append(f"{i}. 假设：{item.get('content', '')}")
            lines.append(f"   验证结果：{'通过' if item.get('passed', False) else '失败'}")
            if item.get('failure_reason'):
                lines.append(f"   失败原因：{item.get('failure_reason', '')}")

        return "\n".join(lines)

    def _format_similar_experiences(self, experiences, is_success: bool) -> str:
        if not experiences:
            return ""

        header = "\n## 历史成功经验\n" if is_success else "\n## 历史失败经验（需避免）\n"
        lines = [header]

        for i, exp in enumerate(experiences, 1):
            lines.append(f"{i}. [{exp.status.value}] {exp.similarity_key}")
            lines.append(f"   材料：{exp.material}，刀具：{exp.tool}，工序：{exp.operation}")
            lines.append(f"   参数：{json.dumps(exp.params, ensure_ascii=False)}")
            lines.append(f"   结果：{json.dumps(exp.results, ensure_ascii=False)}")
            if exp.extracted_rules:
                lines.append(f"   提取规则：{'; '.join(exp.extracted_rules)}")

        return "\n".join(lines)
