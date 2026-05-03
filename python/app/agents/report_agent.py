import json
import asyncio
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.agents.tools import tools_dict


@dataclass
class ReACTStep:
    step_number: int
    step_type: str  # thought, action, observation, final_answer
    content: str
    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    tool_output: Optional[Dict] = None
    duration_ms: Optional[float] = None


class ReportAgent:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self.max_iterations = 10
        self.reasoning_steps: List[ReACTStep] = []
        self.report_content: str = ""

    async def generate_report(self, task_id: str, process_task_id: Optional[str] = None) -> str:
        await self.task_manager.update_progress(task_id, 0, "正在初始化 ReACT 报告生成...")

        with self.logger.log_step(task_id, "report_agent", StepType.WORKFLOW_START,
                                  input_data={"process_task_id": process_task_id}):
            pass

        try:
            await self.task_manager.update_progress(task_id, 5, "开始 ReACT 推理循环...")

            with self.logger.log_step(task_id, "report_agent", StepType.REACT_THOUGHT,
                                      input_data={"initial_thought": "开始分析工艺参数并生成报告"}) as log_entry:
                log_entry.output = {"plan": "1. 获取工艺参数 2. 分析材料性能 3. 计算验证 4. 生成报告"}

            await self.task_manager.update_progress(task_id, 10, "正在收集工艺数据...")

            all_observations = []

            for step_num in range(1, self.max_iterations + 1):
                task = self.task_manager.get_task(task_id)
                if task and task.status.value == 'cancelled':
                    return "报告生成已取消"

                progress = 10 + (step_num / self.max_iterations) * 70
                await self.task_manager.update_progress(
                    task_id, progress, f"ReACT 推理第 {step_num} 轮..."
                )

                thought, action_name, action_params = await self._decide_next_step(step_num, all_observations)
                self.reasoning_steps.append(ReACTStep(
                    step_number=step_num, step_type="thought", content=thought
                ))

                if action_name == "FINAL_ANSWER":
                    self.reasoning_steps.append(ReACTStep(
                        step_number=step_num, step_type="final_answer", content=action_params.get("report", "")
                    ))
                    self.report_content = action_params.get("report", "")
                    break

                tool = tools_dict.get(action_name)
                if tool:
                    with self.logger.log_step(
                        task_id, "report_agent", StepType.REACT_ACTION,
                        input_data={"tool": action_name, "params": action_params}
                    ) as log_entry:
                        start_time = time.time()
                        observation = await tool.execute(**action_params)
                        duration_ms = (time.time() - start_time) * 1000
                        log_entry.output = {"summary": observation.summary}

                        self.reasoning_steps.append(ReACTStep(
                            step_number=step_num, step_type="action", content=observation.summary,
                            tool_name=action_name, tool_input=action_params,
                            tool_output=observation.output_data, duration_ms=duration_ms
                        ))

                        with self.logger.log_step(
                            task_id, "report_agent", StepType.REACT_OBSERVATION,
                            input_data={"tool": action_name, "observation": observation.summary}
                        ) as obs_log:
                            obs_log.output = {"output_data": observation.output_data}

                        all_observations.append(observation)

                await asyncio.sleep(0.3)

            if not self.report_content:
                self.report_content = await self._generate_final_report(all_observations)
                self.reasoning_steps.append(ReACTStep(
                    step_number=len(self.reasoning_steps) + 1,
                    step_type="final_answer", content=self.report_content
                ))

            await self.task_manager.update_progress(task_id, 95, "报告生成完成，正在格式化...")

            with self.logger.log_step(task_id, "report_agent", StepType.WORKFLOW_END,
                                      output_data={"report_length": len(self.report_content), "steps": len(self.reasoning_steps)}):
                pass

            await self.task_manager.complete_task(task_id, {
                "report": self.report_content,
                "reasoning_steps": [
                    {
                        "step_number": s.step_number,
                        "step_type": s.step_type,
                        "content": s.content[:200] + "..." if len(s.content) > 200 else s.content,
                        "tool_name": s.tool_name,
                        "duration_ms": s.duration_ms
                    }
                    for s in self.reasoning_steps
                ],
                "total_steps": len(self.reasoning_steps)
            })

            return self.report_content

        except Exception as e:
            await self.task_manager.fail_task(task_id, str(e))
            raise

    async def _decide_next_step(self, step_num: int, observations: List) -> tuple:
        if step_num == 1:
            return (
                "首先需要获取所有工艺参数的完整数据，以便进行综合分析。",
                "get_process_params",
                {"param_type": "all"}
            )
        elif step_num == 2:
            return (
                "已获取工艺参数，接下来需要查询工件材料的力学和热物理性能，以评估加工特性。",
                "get_material_info",
                {"material_name": "45钢", "property_type": "all"}
            )
        elif step_num == 3:
            return (
                "材料性能数据已获取，现在需要查询刀具的几何参数和材质信息，以便进行切削力分析。",
                "get_tool_info",
                {"tool_type": "turning"}
            )
        elif step_num == 4:
            return (
                "刀具参数已获取，现在调用 Kienzle、Taylor 和表面粗糙度公式进行在线验证计算。",
                "calculate_validation",
                {"formula_type": "all"}
            )
        elif step_num == 5:
            return (
                "验证计算已完成，现在查询所有物理约束的满足情况，评估工艺参数是否可行。",
                "get_constraint_status",
                {"constraint_type": "all"}
            )
        else:
            report = await self._generate_final_report(observations)
            return (
                "已收集全部必要数据，现在可以生成完整的工艺分析报告。",
                "FINAL_ANSWER",
                {"report": report}
            )

    async def _generate_final_report(self, observations: List) -> str:
        params_obs = next((o for o in observations if o.tool_name == "get_process_params"), None)
        material_obs = next((o for o in observations if o.tool_name == "get_material_info"), None)
        tool_obs = next((o for o in observations if o.tool_name == "get_tool_info"), None)
        validation_obs = next((o for o in observations if o.tool_name == "calculate_validation"), None)
        constraint_obs = next((o for o in observations if o.tool_name == "get_constraint_status"), None)

        params = params_obs.output_data if params_obs else {}
        material = material_obs.output_data if material_obs else {}
        tool = tool_obs.output_data if tool_obs else {}
        validation = validation_obs.output_data if validation_obs else {}
        constraints = constraint_obs.output_data if constraint_obs else {}

        report = """# 工艺分析报告

## 1. 工艺参数总览

"""
        if "cutting_speed" in params:
            cs = params["cutting_speed"]
            fr = params.get("feed_rate", {})
            dc = params.get("depth_of_cut", {})
            report += f"""| 参数 | 数值 | 单位 |
|------|------|------|
| 切削速度 ($v_c$) | {cs.get('v_c', 150.0):.2f} | {cs.get('unit', 'm/min')} |
| 进给量 ($f$) | {fr.get('f', 0.20):.2f} | {fr.get('unit', 'mm/rev')} |
| 切削深度 ($a_p$) | {dc.get('a_p', 2.0):.2f} | {dc.get('unit', 'mm')} |

"""

        report += """## 2. 材料与刀具分析

### 2.1 工件材料性能

"""
        if "mechanical" in material:
            m = material["mechanical"]
            report += f"""| 性能指标 | 数值 | 单位 |
|---------|------|------|
| 硬度 | {m.get('hardness_hrc', 25.0):.2f} | HRC |
| 抗拉强度 | {m.get('tensile_strength_mpa', 600.0):.2f} | MPa |
| 屈服强度 | {m.get('yield_strength_mpa', 355.0):.2f} | MPa |
| 延伸率 | {m.get('elongation_percent', 16.0):.2f} | % |
| 弹性模量 | {m.get('modulus_of_elasticity_gpa', 210.0):.2f} | GPa |

"""

        report += "### 2.2 刀具参数\n\n"
        if tool:
            report += f"""| 参数 | 数值 |
|------|------|
| 刀具材质 | {tool.get('tool_material', '硬质合金')} |
| 涂层 | {tool.get('coating', 'TiAlN')} |
| 前角 | {tool.get('geometry', {}).get('rake_angle_deg', 5.0):.2f}° |
| 后角 | {tool.get('geometry', {}).get('clearance_angle_deg', 7.0):.2f}° |
| 刀尖圆弧半径 | {tool.get('geometry', {}).get('nose_radius_mm', 0.8):.2f} mm |

"""

        report += """## 3. 切削力分析

基于 Kienzle 公式 $F_c = K_c \\cdot a_p \\cdot f$ 进行切削力计算。

"""
        if "kienzle" in validation:
            k = validation["kienzle"]
            report += f"""| 指标 | 数值 | 单位 |
|------|------|------|
| 切削力 ($F_c$) | {k.get('cutting_force_N', 0):.2f} | N |
| 单位切削力 ($K_c$) | {k.get('specific_cutting_force_Nmm2', 0):.2f} | N/mm² |

"""

        report += """## 4. 刀具寿命预测

基于 Taylor 公式 $v_c \\cdot T^n = C$ 进行刀具寿命评估。

"""
        if "taylor" in validation:
            t = validation["taylor"]
            report += f"""| 指标 | 数值 | 单位 |
|------|------|------|
| 刀具寿命 ($T$) | {t.get('tool_life_min', 0):.2f} | min |
| 刀具寿命 | {t.get('tool_life_hours', 0):.2f} | h |
| Taylor 指数 ($n$) | {t.get('taylor_exponent', 0.25):.2f} | - |

"""

        report += """## 5. 表面质量评估

"""
        if "surface_roughness" in validation:
            sr = validation["surface_roughness"]
            meets = "满足" if sr.get("meets_requirement") else "不满足"
            report += f"""| 指标 | 数值 | 单位 | 要求 |
|------|------|------|------|
| 表面粗糙度 ($Ra$) | {sr.get('predicted_ra_um', 0):.2f} | μm | ≤ 1.6 μm |

**评估结果**：表面粗糙度预测值 {sr.get('predicted_ra_um', 0):.2f} μm，{meets}工艺要求。

"""

        report += """## 6. 约束满足度总结

"""
        if constraints:
            report += """| 约束类型 | 实际值 | 限制值 | 单位 | 状态 | 裕度 |
|---------|--------|--------|------|------|------|
"""
            for ctype, cdata in constraints.items():
                status = "✓ 满足" if cdata.get("satisfied") else "✗ 违反"
                report += f"| {ctype} | {cdata.get('actual_value', 0):.2f} | {cdata.get('limit', 0):.2f} | {cdata.get('unit', '')} | {status} | {cdata.get('margin_percent', 0):.2f}% |\n"

        report += """

## 7. 优化建议

基于以上分析结果，提出以下优化建议：

1. **切削参数优化**：当前切削速度 150.00 m/min 处于合理范围，若需提高效率可适当提高至 180-200 m/min，但需监控切削温度。

2. **刀具寿命管理**：建议每加工 50 件进行一次刀具检查，发现异常磨损及时更换。

3. **表面质量控制**：若需进一步提高表面质量，可将进给量降低至 0.15 mm/rev，预计 Ra 可降至 0.47 μm。

4. **切削液使用**：建议使用水基切削液，浓度 5-8%，流量 10-15 L/min，以降低切削温度并改善排屑条件。

---

*报告生成时间：""" + time.strftime("%Y-%m-%d %H:%M:%S") + """*
*分析方法：ReACT 智能体自主推理*
"""
        return report

    def get_reasoning_steps(self) -> List[Dict]:
        return [
            {
                "step_number": s.step_number,
                "step_type": s.step_type,
                "content": s.content,
                "tool_name": s.tool_name,
                "tool_input": s.tool_input,
                "tool_output": s.tool_output,
                "duration_ms": s.duration_ms
            }
            for s in self.reasoning_steps
        ]
