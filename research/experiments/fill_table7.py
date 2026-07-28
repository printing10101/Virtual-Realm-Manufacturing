"""
生成论文表7（SLD-as-Prompt 模板）内容。

学术诚信说明（重要）：
    本脚本**不再手工硬编码**任何工艺场景对话或实验数值。
    表7的内容按以下原则生成：
      1. **真实查询行**：从 ``python/experiments/results/`` 下的真实实验结果
         JSON 文件（stability_lobes_results.json、main_comparison_results.json、
         cross_condition_results.json 等）**自动派生**数值；
      2. **演示样例1/2/3 行**：明确标注为"人工设计的 prompt 模板示例"，
         仅用于展示 SLD-as-Prompt 模板的对话形式能力，**不声称对应真实实验**；
      3. 脚本输出为 Markdown 表格 + JSON 配置文件，**不修改任何 .docx 论文文件**，
         论文作者需人工审阅后决定是否采用。

输出文件：
    - ``results/table7_sld_prompt_template.md``  （Markdown 表格，供人工审阅）
    - ``results/table7_sld_prompt_template.json`` （结构化数据，供下游程序使用）

数据来源（真实实验结果）：
    - ``results/stability_lobes_results.json``  ：SLD 对比实验的 a_lim 误差
    - ``results/main_comparison_results.json``  ：多数据集模型对比 MAE/RMSE/R²
    - ``results/cross_condition_results.json``  ：跨工况/跨材料泛化性能
    - ``results/main_results.json``             ：合成/工业数据集主结果
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 实验结果目录（相对本脚本位置）
_RESULTS_DIR = Path(__file__).resolve().parent / "results"
_OUTPUT_DIR = _RESULTS_DIR


def _load_json(filename: str) -> dict[str, Any] | None:
    """安全加载实验结果 JSON。

    Args:
        filename: results 目录下的 JSON 文件名

    Returns:
        解析后的字典；若文件不存在或解析失败则返回 None
    """
    file_path = _RESULTS_DIR / filename
    if not file_path.exists():
        logger.warning("实验结果文件不存在: %s", file_path)
        return None
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("读取实验结果 JSON 失败 (%s): %s", file_path, e)
        return None


def _fmt(value: float, precision: int = 3) -> str:
    """格式化浮点数为字符串，处理 NaN/Inf。"""
    try:
        if value != value:  # NaN
            return "N/A"
        if abs(value) == float("inf"):
            return "∞"
        return f"{value:.{precision}f}"
    except (TypeError, ValueError):
        return "N/A"


def _derive_real_query_row(
    sld_results: dict | None,
    main_results: dict | None,
    cross_results: dict | None,
) -> dict[str, str]:
    """从真实实验结果派生表7的"真实查询"行内容。

    Args:
        sld_results: stability_lobes_results.json 解析结果
        main_results: main_comparison_results.json 解析结果
        cross_results: cross_condition_results.json 解析结果

    Returns:
        包含 user / assistant / data_source 三键的字典
    """
    # —— 数值提取（带降级回退）——
    a_lim_mae: float | None = None
    a_lim_pred_range: tuple[float, float] | None = None
    speed_range: tuple[float, float] | None = None
    if sld_results is not None:
        metrics = sld_results.get("metrics", {})
        a_lim_mae = metrics.get("mae_a_lim")
        lobe_summary = sld_results.get("lobe_data_summary", {})
        pred_range = lobe_summary.get("a_lim_predicted_range")
        if isinstance(pred_range, list) and len(pred_range) == 2:
            a_lim_pred_range = (pred_range[0], pred_range[1])
        spd_range = lobe_summary.get("speed_range")
        if isinstance(spd_range, list) and len(spd_range) == 2:
            speed_range = (spd_range[0], spd_range[1])

    # DL-LNN 在 PHM2010 上的表现（真实数据集）
    ctltc_mae_phm: float | None = None
    ctltc_rmse_phm: float | None = None
    if main_results is not None:
        phm_block = main_results.get("PHM2010", {})
        ctltc_stats = phm_block.get("DL-LNN", {})
        ctltc_mae_phm = ctltc_stats.get("MAE")
        ctltc_rmse_phm = ctltc_stats.get("RMSE")

    # 跨工况平均 PCC（DL-LNN）
    ctltc_pcc_loco: float | None = None
    if cross_results is not None:
        loco_block = cross_results.get("LOCO", {})
        avg_block = loco_block.get("Average", {})
        ctltc_stats = avg_block.get("DL-LNN", {})
        ctltc_pcc_loco = ctltc_stats.get("PCC")

    # —— 派生查询场景 ——
    # 选择 SLD 实验网格中点作为"查询工况"（避免手工指定任意转速）
    if speed_range is not None:
        query_speed = round((speed_range[0] + speed_range[1]) / 2.0)
    else:
        query_speed = None

    # 派生 a_lim 参考值（取预测范围中点）
    if a_lim_pred_range is not None:
        a_lim_ref = (a_lim_pred_range[0] + a_lim_pred_range[1]) / 2.0
    else:
        a_lim_ref = None

    # —— 构造对话内容（数据驱动，非手工编造）——
    user_parts: list[str] = []
    if query_speed is not None:
        user_parts.append(f"n = {query_speed:,} r/min（SLD 实验网格中点工况）")
    user_parts.append("ap 待评估，请基于 DL-LNN 推理给出稳定性判定与极限切深。")

    assistant_parts: list[str] = []
    if a_lim_ref is not None:
        assistant_parts.append(
            f"根据 DL-LNN 在 SLD 网格上的预测，参考极限切深 "
            f"a_lim ≈ {_fmt(a_lim_ref, 2)} mm"
        )
    if a_lim_mae is not None:
        assistant_parts.append(
            f"（模型与 Tlusty 理论 a_lim 的 MAE = {_fmt(a_lim_mae, 3)} mm）"
        )
    if ctltc_mae_phm is not None and ctltc_rmse_phm is not None:
        assistant_parts.append(
            f"在 PHM2010 真实数据集上 DL-LNN 的 MAE = "
            f"{_fmt(ctltc_mae_phm, 3)} mm，RMSE = "
            f"{_fmt(ctltc_rmse_phm, 3)} mm"
        )
    if ctltc_pcc_loco is not None:
        assistant_parts.append(
            f"跨工况平均 PCC = {_fmt(ctltc_pcc_loco, 4)}（LOCO 评估）"
        )
    if a_lim_ref is not None:
        # 给出 15% 安全裕量建议（自动派生，非手工指定）
        safe_ap = 0.85 * a_lim_ref
        assistant_parts.append(
            f"建议：将 ap 控制在 {_fmt(safe_ap, 2)} mm 以内（保留 15% 安全裕量）。"
        )

    return {
        "user": "；".join(user_parts) + "。",
        "assistant": " ".join(assistant_parts) if assistant_parts else (
            "实验结果数据不足，无法派生 DL-LNN 推理结论。"
        ),
        "data_source": "real_experiment_results",
    }


def _build_demo_samples() -> list[dict[str, str]]:
    """构造演示样例1/2/3（人工设计的 prompt 模板示例）。

    学术诚信说明：
        这些样例**仅为展示 SLD-as-Prompt 模板的对话形式**，
        不对应任何具体真实实验。在论文中应明确标注为"模板示例"。
    """
    return [
        {
            "scenario": "演示样例1：转速过高场景",
            "user": "[模板示例] 用户描述：加工过程中出现明显振纹，"
                    "当前主轴转速较高，希望诊断原因。",
            "assistant": "[模板示例] SLD-as-Prompt 模板响应：根据输入工况，"
                    "推断当前转速可能处于稳定性叶瓣峰值附近，"
                    "建议调整至相邻叶瓣谷值转速并减小切深。",
            "data_source": "synthetic_template_example",
        },
        {
            "scenario": "演示样例2：切深过大场景",
            "user": "[模板示例] 用户描述：固定转速下逐步加大轴向切深，"
                    "出现颤振后减小切深即消失。",
            "assistant": "[模板示例] SLD-as-Prompt 模板响应：当前切深可能已超过"
                    " SLD 预测的极限切深 a_lim，建议降至安全裕量内。",
            "data_source": "synthetic_template_example",
        },
        {
            "scenario": "演示样例3：模态参数失配场景",
            "user": "[模板示例] 用户描述：缺少机床模态参数（k、m、ζ），"
                    "需评估稳定性。",
            "assistant": "[模板示例] SLD-as-Prompt 模板响应：缺少模态参数时模型"
                    "退化为粗略 SLD；建议先通过锤击法测定模态参数后重新校核。",
            "data_source": "synthetic_template_example",
        },
    ]


def _build_table7_payload() -> dict[str, Any]:
    """构建表7的完整结构化内容。

    Returns:
        包含 demo_samples / real_query / metadata 三键的字典
    """
    sld_results = _load_json("stability_lobes_results.json")
    main_results = _load_json("main_comparison_results.json")
    cross_results = _load_json("cross_condition_results.json")

    real_query = _derive_real_query_row(sld_results, main_results, cross_results)
    demo_samples = _build_demo_samples()

    return {
        "table_id": "table7",
        "table_title": "SLD-as-Prompt 模板对话样例",
        "metadata": {
            "data_sources": [
                "results/stability_lobes_results.json",
                "results/main_comparison_results.json",
                "results/cross_condition_results.json",
            ],
            "academic_integrity_note": (
                "演示样例1/2/3 为人工设计的 prompt 模板示例，"
                "仅展示对话形式，不对应真实实验；"
                "真实查询行的数值从实验结果 JSON 自动派生。"
            ),
            "demo_sample_disclaimer": (
                "demo_samples 的 data_source = 'synthetic_template_example'，"
                "在论文中应明确标注为模板示例。"
            ),
        },
        "demo_samples": demo_samples,
        "real_query": real_query,
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    """将表7 payload 渲染为 Markdown 表格字符串。"""
    lines: list[str] = []
    lines.append(f"# {payload['table_title']}\n")
    lines.append("> **学术诚信声明**：")
    lines.append(f"> {payload['metadata']['academic_integrity_note']}")
    lines.append("")
    lines.append("**数据来源**：")
    for src in payload["metadata"]["data_sources"]:
        lines.append(f"- `{src}`")
    lines.append("")

    lines.append("## 表7 内容\n")
    lines.append("| 行 | 角色 | 内容 | 数据来源 |")
    lines.append("|----|------|------|----------|")

    # 演示样例
    for i, sample in enumerate(payload["demo_samples"], start=1):
        lines.append(
            f"| {i} | User | {sample['user']} | "
            f"{sample['data_source']} |"
        )
        lines.append(
            f"| {i} | Assistant | {sample['assistant']} | "
            f"{sample['data_source']} |"
        )

    # 真实查询
    rq = payload["real_query"]
    lines.append(
        f"| 真实查询 | User | {rq['user']} | {rq['data_source']} |"
    )
    lines.append(
        f"| 真实查询 | Assistant | {rq['assistant']} | "
        f"{rq['data_source']} |"
    )

    lines.append("")
    lines.append(
        "## 说明\n"
    )
    lines.append(
        f"- {payload['metadata']['demo_sample_disclaimer']}"
    )
    lines.append(
        "- 真实查询行的数值（a_lim、MAE、RMSE、PCC 等）均来自实验结果 JSON，"
        "未做任何手工编造。"
    )
    lines.append(
        "- 本脚本不修改任何 .docx 论文文件；论文作者需人工审阅后决定是否采用。"
    )

    return "\n".join(lines)


def main() -> None:
    """主入口：从真实实验结果派生表7内容，输出 Markdown + JSON。"""
    print("=" * 80)
    print("生成表7 SLD-as-Prompt 模板内容（数据驱动，非手工硬编码）")
    print("=" * 80)

    payload = _build_table7_payload()

    # 输出 JSON
    json_path = _OUTPUT_DIR / "table7_sld_prompt_template.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] JSON 已生成: {json_path}")

    # 输出 Markdown
    md_path = _OUTPUT_DIR / "table7_sld_prompt_template.md"
    md_content = _render_markdown(payload)
    md_path.write_text(md_content, encoding="utf-8")
    print(f"[OK] Markdown 已生成: {md_path}")

    # 控制台预览
    print("\n--- Markdown 预览 ---")
    print(md_content)
    print("=" * 80)
    print("表7内容生成完成。请人工审阅后决定是否写入论文。")
    print("=" * 80)


if __name__ == "__main__":
    main()
