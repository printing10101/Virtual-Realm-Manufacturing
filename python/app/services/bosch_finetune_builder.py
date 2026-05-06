import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from app.data.bosch_cnc_loader import BoschCNCDataLoader
from app.rag.bosch_knowledge_builder import PROCESS_NAMES

CATEGORY_LABELS = {
    "diagnosis": "工艺诊断",
    "parameter_optimization": "参数优化",
    "comparison": "工序对比",
    "maintenance": "预防性维护",
}

DIAGNOSIS_INSTRUCTIONS = [
    "分析以下{process_cn}工序的振动数据，判断是否存在异常并给出可能原因。",
    "根据以下振动特征，诊断{machine}机床{process_cn}工序的运行状态。",
    "请评估以下{process_cn}工序的振动数据是否正常，并说明判断依据。",
    "基于提供的振动数据，分析{machine}机床{process_cn}工序是否存在潜在问题。",
]

PARAM_OPT_INSTRUCTIONS = [
    "根据振动数据特征，建议如何优化{machine}机床{process_cn}工序的切削参数？",
    "当前{process_cn}工序振动数据如下，请给出切削参数优化建议。",
    "分析以下振动数据，提出{process_cn}工序的工艺参数改进方案。",
]

COMPARISON_INSTRUCTIONS = [
    "对比{machine_a}和{machine_b}机床上{process_cn}工序的振动特征差异。",
    "请分析{machine_a}与{machine_b}机床执行{process_cn}工序时的振动数据区别。",
    "比较{process_cn}工序在{machine_a}和{machine_b}两台机床上的加工状态差异。",
]

MAINTENANCE_INSTRUCTIONS = [
    "根据过去{months}个月的振动趋势数据，判断{machine}机床是否需要预防性维护。",
    "基于{machine}机床近期的振动监测数据，评估其设备健康状态并给出维护建议。",
    "分析{machine}机床{process_cn}工序的振动趋势，预测是否需要提前维护。",
]


class BoschFinetuneBuilder:
    """将 Bosch CNC 数据集转化为 LLM 微调样本"""

    def __init__(self, data_dir: str = "python/app/data/datasets/bosch_cnc"):
        self.data_dir = data_dir
        self.loader = BoschCNCDataLoader(data_dir=data_dir)
        self._cache: dict[str, Any] = {}

    def _get_process_features(self) -> dict[str, dict]:
        if "process_features" in self._cache:
            return self._cache["process_features"]

        summary = self.loader.get_dataset_summary()
        machines = summary.get("available_machines", [])
        processes = summary.get("available_processes", [])

        process_features: dict[str, dict] = {}

        for machine in machines:
            for process in processes:
                key = f"{machine}_{process}"
                good_samples = self.loader.load_dataset(
                    machines=[machine], processes=[process], labels=["good"]
                )
                bad_samples = self.loader.load_dataset(
                    machines=[machine], processes=[process], labels=["bad"]
                )

                if not good_samples and not bad_samples:
                    continue

                good_feats = [self.loader.extract_features(s["data"]) for s in good_samples] if good_samples else []
                bad_feats = [self.loader.extract_features(s["data"]) for s in bad_samples] if bad_samples else []

                process_features[key] = {
                    "machine": machine,
                    "process": process,
                    "process_cn": PROCESS_NAMES.get(process, process),
                    "good_count": len(good_samples),
                    "bad_count": len(bad_samples),
                    "good_feats": good_feats,
                    "bad_feats": bad_feats,
                }

        self._cache["process_features"] = process_features
        return process_features

    def _compute_axis_stats(self, feats: list[dict], axis: str) -> dict:
        rms_vals = [f.get(f"time_{axis}_rms", 0) for f in feats]
        rms_vals = [v for v in rms_vals if np.isfinite(v)]
        freq_vals = [f.get(f"freq_{axis}_dominant_freq", 0) for f in feats]
        freq_vals = [v for v in freq_vals if np.isfinite(v)]
        energy_vals = [f.get(f"cross_{axis}_energy_ratio", 0) for f in feats]
        energy_vals = [v for v in energy_vals if np.isfinite(v)]

        return {
            "rms_min": float(np.min(rms_vals)) if rms_vals else 0,
            "rms_max": float(np.max(rms_vals)) if rms_vals else 0,
            "rms_mean": float(np.mean(rms_vals)) if rms_vals else 0,
            "rms_std": float(np.std(rms_vals)) if rms_vals else 0,
            "freq_min": float(np.min(freq_vals)) if freq_vals else 0,
            "freq_max": float(np.max(freq_vals)) if freq_vals else 0,
            "freq_mean": float(np.mean(freq_vals)) if freq_vals else 0,
            "energy_mean": float(np.mean(energy_vals)) * 100 if energy_vals else 0,
        }

    def _format_vibration_input(
        self, machine: str, process: str, process_cn: str, stats: dict, is_abnormal: bool = False
    ) -> str:
        lines = [
            f"工序：{process}（{process_cn}），机床：{machine}",
            f"振动数据特征：",
            f"- X轴 RMS: {stats['x']['rms_mean']:.4f}g（范围 {stats['x']['rms_min']:.4f}~{stats['x']['rms_max']:.4f}g）",
            f"- Y轴 RMS: {stats['y']['rms_mean']:.4f}g（范围 {stats['y']['rms_min']:.4f}~{stats['y']['rms_max']:.4f}g）",
            f"- Z轴 RMS: {stats['z']['rms_mean']:.4f}g（范围 {stats['z']['rms_min']:.4f}~{stats['z']['rms_max']:.4f}g）",
            f"- X轴主频: {stats['x']['freq_mean']:.0f}Hz（范围 {stats['x']['freq_min']:.0f}~{stats['x']['freq_max']:.0f}Hz）",
            f"- Y轴主频: {stats['y']['freq_mean']:.0f}Hz（范围 {stats['y']['freq_min']:.0f}~{stats['y']['freq_max']:.0f}Hz）",
            f"- Z轴主频: {stats['z']['freq_mean']:.0f}Hz（范围 {stats['z']['freq_min']:.0f}~{stats['z']['freq_max']:.0f}Hz）",
            f"- 能量分布：X轴 {stats['x']['energy_mean']:.1f}%，Y轴 {stats['y']['energy_mean']:.1f}%，Z轴 {stats['z']['energy_mean']:.1f}%",
        ]
        if is_abnormal:
            lines.append(f"状态标注：异常")
        else:
            lines.append(f"状态标注：正常")
        return "\n".join(lines)

    def _generate_diagnosis_output(self, machine: str, process: str, process_cn: str, good_stats: dict, bad_stats: dict | None, is_abnormal: bool) -> str:
        if not is_abnormal:
            output = (
                f"诊断结果：正常\n\n"
                f"正常分析：\n"
                f"1. 三轴振动幅值均在正常范围内，X轴 RMS {good_stats['x']['rms_mean']:.4f}g，Y轴 RMS {good_stats['y']['rms_mean']:.4f}g，Z轴 RMS {good_stats['z']['rms_mean']:.4f}g\n"
                f"2. 主频分布合理，X轴主频 {good_stats['x']['freq_mean']:.0f}Hz，Y轴主频 {good_stats['y']['freq_mean']:.0f}Hz，Z轴主频 {good_stats['z']['freq_mean']:.0f}Hz\n"
                f"3. 能量分布均衡，X轴 {good_stats['x']['energy_mean']:.1f}%，Y轴 {good_stats['y']['energy_mean']:.1f}%，Z轴 {good_stats['z']['energy_mean']:.1f}%\n\n"
                f"建议措施：\n"
                f"1. 继续维持当前加工参数\n"
                f"2. 定期监测振动数据变化趋势\n"
                f"3. 按标准周期进行刀具检查"
            )
            return output

        if bad_stats is None:
            bad_stats = good_stats

        rms_ratio_x = bad_stats['x']['rms_mean'] / max(good_stats['x']['rms_mean'], 1e-10)
        rms_ratio_y = bad_stats['y']['rms_mean'] / max(good_stats['y']['rms_mean'], 1e-10)
        rms_ratio_z = bad_stats['z']['rms_mean'] / max(good_stats['z']['rms_mean'], 1e-10)
        max_ratio = max(rms_ratio_x, rms_ratio_y, rms_ratio_z)
        max_axis = "X" if rms_ratio_x == max_ratio else ("Y" if rms_ratio_y == max_ratio else "Z")

        freq_shift_x = abs(bad_stats['x']['freq_mean'] - good_stats['x']['freq_mean']) / max(good_stats['x']['freq_mean'], 1e-10) * 100
        freq_shift_y = abs(bad_stats['y']['freq_mean'] - good_stats['y']['freq_mean']) / max(good_stats['y']['freq_mean'], 1e-10) * 100
        freq_shift_z = abs(bad_stats['z']['freq_mean'] - good_stats['z']['freq_mean']) / max(good_stats['z']['freq_mean'], 1e-10) * 100
        max_freq_shift = max(freq_shift_x, freq_shift_y, freq_shift_z)

        energy_shift_z = abs(bad_stats['z']['energy_mean'] - good_stats['z']['energy_mean'])

        severity = "轻度" if max_ratio <= 2.0 else ("中度" if max_ratio <= 4.0 else "重度")

        output = (
            f"诊断结果：异常（{severity}）\n\n"
            f"异常分析：\n"
            f"1. 三轴振动幅值均超出正常范围 {rms_ratio_x:.1f}~{rms_ratio_z:.1f} 倍，其中 {max_axis} 轴最为显著\n"
            f"2. 主频偏移最大 {max_freq_shift:.1f}%，偏离正常范围，超过 15% 警戒线\n"
            f"3. Z 轴能量占比变化 {energy_shift_z:.1f}%，可能存在轴向力异常\n\n"
            f"可能原因：\n"
            f"1. 刀具{'严重' if max_ratio > 4.0 else '中度' if max_ratio > 2.0 else '轻微'}磨损（振动幅值全面增大）\n"
            f"2. 主轴轴承间隙过大（主频偏移）\n"
            f"3. 工件装夹不稳定（Z 轴异常）\n\n"
            f"建议措施：\n"
            f"1. {'立即停机检查' if max_ratio > 4.0 else '近期安排检查'}刀具磨损情况\n"
            f"2. 测量主轴径向跳动\n"
            f"3. 检查工件装夹力矩"
        )
        return output

    def generate_diagnosis_samples(self) -> list[dict]:
        """生成工艺诊断类微调样本"""
        samples = []
        process_features = self._get_process_features()

        for key, data in process_features.items():
            machine = data["machine"]
            process = data["process"]
            process_cn = data["process_cn"]
            good_feats = data["good_feats"]
            bad_feats = data["bad_feats"]

            if not good_feats:
                continue

            good_stats = {
                axis: self._compute_axis_stats(good_feats, axis)
                for axis in ["x", "y", "z"]
            }

            for i in range(min(3, len(good_feats))):
                subset = random.sample(good_feats, min(10, len(good_feats)))
                subset_stats = {
                    axis: self._compute_axis_stats(subset, axis)
                    for axis in ["x", "y", "z"]
                }

                instruction = random.choice(DIAGNOSIS_INSTRUCTIONS).format(
                    machine=machine, process=process, process_cn=process_cn
                )
                input_text = self._format_vibration_input(
                    machine, process, process_cn, subset_stats, is_abnormal=False
                )
                output_text = self._generate_diagnosis_output(
                    machine, process, process_cn, good_stats, None, is_abnormal=False
                )

                samples.append({
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "source": {
                        "machine": machine,
                        "process": process,
                        "timeframe": "aggregated",
                        "label": "good",
                    },
                    "category": "diagnosis",
                })

            if bad_feats:
                bad_stats = {
                    axis: self._compute_axis_stats(bad_feats, axis)
                    for axis in ["x", "y", "z"]
                }

                for i in range(min(3, len(bad_feats))):
                    subset = random.sample(bad_feats, min(10, len(bad_feats)))
                    subset_stats = {
                        axis: self._compute_axis_stats(subset, axis)
                        for axis in ["x", "y", "z"]
                    }

                    instruction = random.choice(DIAGNOSIS_INSTRUCTIONS).format(
                        machine=machine, process=process, process_cn=process_cn
                    )
                    input_text = self._format_vibration_input(
                        machine, process, process_cn, subset_stats, is_abnormal=True
                    )
                    output_text = self._generate_diagnosis_output(
                        machine, process, process_cn, good_stats, bad_stats, is_abnormal=True
                    )

                    samples.append({
                        "instruction": instruction,
                        "input": input_text,
                        "output": output_text,
                        "source": {
                            "machine": machine,
                            "process": process,
                            "timeframe": "aggregated",
                            "label": "bad",
                        },
                        "category": "diagnosis",
                    })

        return samples

    def _generate_parameter_optimization_output(
        self, machine: str, process: str, process_cn: str, good_stats: dict, bad_stats: dict
    ) -> str:
        rms_ratio_x = bad_stats['x']['rms_mean'] / max(good_stats['x']['rms_mean'], 1e-10)
        max_ratio = max(rms_ratio_x, bad_stats['y']['rms_mean'] / max(good_stats['y']['rms_mean'], 1e-10))

        if max_ratio > 3.0:
            speed_adj = "-15%"
            feed_adj = "-20%"
            depth_adj = "-10%"
        elif max_ratio > 2.0:
            speed_adj = "-10%"
            feed_adj = "-15%"
            depth_adj = "-5%"
        else:
            speed_adj = "-5%"
            feed_adj = "-10%"
            depth_adj = "-3%"

        output = (
            f"当前振动状态评估：\n"
            f"1. 振动幅值超出正常范围 {max_ratio:.1f} 倍，处于{'严重' if max_ratio > 3.0 else '中度' if max_ratio > 2.0 else '轻微'}异常状态\n"
            f"2. 三轴振动不均衡，需要调整切削参数降低振动\n\n"
            f"切削参数调整建议：\n"
            f"1. 切削速度：建议降低 {speed_adj}，减小切削力\n"
            f"2. 进给速度：建议降低 {feed_adj}，降低每齿切削负荷\n"
            f"3. 切削深度：建议降低 {depth_adj}，分散切削力\n\n"
            f"预期改善效果：\n"
            f"1. 振动幅值预计可降低 30%~50%，恢复到正常范围的 1.5 倍以内\n"
            f"2. 主频偏移减小，频谱分布更加集中\n"
            f"3. 加工表面质量提升，刀具寿命延长 20%~30%\n\n"
            f"注意事项：\n"
            f"1. 参数调整后需重新监测振动数据，确认改善效果\n"
            f"2. 若振动仍未改善，建议检查刀具磨损和主轴状态\n"
            f"3. 优化后的参数需记录到工艺知识库，供后续参考"
        )
        return output

    def generate_parameter_optimization_samples(self) -> list[dict]:
        """生成工艺参数优化类微调样本"""
        samples = []
        process_features = self._get_process_features()

        for key, data in process_features.items():
            machine = data["machine"]
            process = data["process"]
            process_cn = data["process_cn"]
            good_feats = data["good_feats"]
            bad_feats = data["bad_feats"]

            if not good_feats or not bad_feats:
                continue

            good_stats = {
                axis: self._compute_axis_stats(good_feats, axis)
                for axis in ["x", "y", "z"]
            }
            bad_stats = {
                axis: self._compute_axis_stats(bad_feats, axis)
                for axis in ["x", "y", "z"]
            }

            for i in range(min(2, len(bad_feats))):
                instruction = random.choice(PARAM_OPT_INSTRUCTIONS).format(
                    machine=machine, process=process, process_cn=process_cn
                )

                subset = random.sample(bad_feats, min(10, len(bad_feats)))
                subset_stats = {
                    axis: self._compute_axis_stats(subset, axis)
                    for axis in ["x", "y", "z"]
                }
                input_text = self._format_vibration_input(
                    machine, process, process_cn, subset_stats, is_abnormal=True
                )
                output_text = self._generate_parameter_optimization_output(
                    machine, process, process_cn, good_stats, bad_stats
                )

                samples.append({
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "source": {
                        "machine": machine,
                        "process": process,
                        "timeframe": "aggregated",
                        "label": "bad",
                    },
                    "category": "parameter_optimization",
                })

        return samples

    def _generate_comparison_output(
        self, machine_a: str, machine_b: str, process: str, process_cn: str,
        stats_a: dict, stats_b: dict
    ) -> str:
        rms_diff_x = abs(stats_a['x']['rms_mean'] - stats_b['x']['rms_mean'])
        rms_diff_y = abs(stats_a['y']['rms_mean'] - stats_b['y']['rms_mean'])
        rms_diff_z = abs(stats_a['z']['rms_mean'] - stats_b['z']['rms_mean'])
        max_diff = max(rms_diff_x, rms_diff_y, rms_diff_z)
        max_diff_axis = "X" if rms_diff_x == max_diff else ("Y" if rms_diff_y == max_diff else "Z")

        freq_diff_x = abs(stats_a['x']['freq_mean'] - stats_b['x']['freq_mean'])
        freq_diff_y = abs(stats_a['y']['freq_mean'] - stats_b['y']['freq_mean'])
        freq_diff_z = abs(stats_a['z']['freq_mean'] - stats_b['z']['freq_mean'])
        max_freq_diff = max(freq_diff_x, freq_diff_y, freq_diff_z)

        energy_diff_z = abs(stats_a['z']['energy_mean'] - stats_b['z']['energy_mean'])

        output = (
            f"振动特征对比：\n"
            f"1. {machine_a} vs {machine_b} - {process_cn}（{process}）\n"
            f"   X轴 RMS: {stats_a['x']['rms_mean']:.4f}g vs {stats_b['x']['rms_mean']:.4f}g（差异 {rms_diff_x:.4f}g）\n"
            f"   Y轴 RMS: {stats_a['y']['rms_mean']:.4f}g vs {stats_b['y']['rms_mean']:.4f}g（差异 {rms_diff_y:.4f}g）\n"
            f"   Z轴 RMS: {stats_a['z']['rms_mean']:.4f}g vs {stats_b['z']['rms_mean']:.4f}g（差异 {rms_diff_z:.4f}g）\n\n"
            f"差异分析：\n"
            f"1. {max_diff_axis}轴振动幅值差异最大（{max_diff:.4f}g），表明两台机床在该方向的切削力分布不同\n"
            f"2. 主频差异最大 {max_freq_diff:.0f}Hz，说明主轴转速或负载特性存在差异\n"
            f"3. Z轴能量占比差异 {energy_diff_z:.1f}%，反映轴向切削力分布不一致\n\n"
            f"可能的设备状态差异原因：\n"
            f"1. 机床几何精度差异（导轨磨损、丝杠间隙）\n"
            f"2. 主轴轴承状态不同（轴承间隙、润滑状况）\n"
            f"3. 刀具装夹差异（刀具伸出长度、夹持力）\n"
            f"4. 工件装夹方式或定位基准不一致\n\n"
            f"建议措施：\n"
            f"1. 对振动较高的机床进行几何精度检测\n"
            f"2. 统一两台机床的刀具装夹标准\n"
            f"3. 建立机床专属振动基线，分别监控"
        )
        return output

    def generate_comparison_samples(self) -> list[dict]:
        """生成工序对比分析类微调样本"""
        samples = []
        process_features = self._get_process_features()

        machines = set()
        for key, data in process_features.items():
            machines.add(data["machine"])

        machines = list(machines)
        if len(machines) < 2:
            return samples

        for i in range(len(machines)):
            for j in range(i + 1, len(machines)):
                machine_a = machines[i]
                machine_b = machines[j]

                for process in PROCESS_NAMES.keys():
                    key_a = f"{machine_a}_{process}"
                    key_b = f"{machine_b}_{process}"

                    if key_a not in process_features or key_b not in process_features:
                        continue

                    data_a = process_features[key_a]
                    data_b = process_features[key_b]

                    if not data_a["good_feats"] or not data_b["good_feats"]:
                        continue

                    process_cn = data_a["process_cn"]

                    stats_a = {
                        axis: self._compute_axis_stats(data_a["good_feats"], axis)
                        for axis in ["x", "y", "z"]
                    }
                    stats_b = {
                        axis: self._compute_axis_stats(data_b["good_feats"], axis)
                        for axis in ["x", "y", "z"]
                    }

                    instruction = random.choice(COMPARISON_INSTRUCTIONS).format(
                        machine_a=machine_a, machine_b=machine_b,
                        process=process, process_cn=process_cn
                    )
                    input_text = (
                        f"{machine_a}机床{process_cn}（{process}）振动特征：\n"
                        f"- X轴 RMS: {stats_a['x']['rms_mean']:.4f}g\n"
                        f"- Y轴 RMS: {stats_a['y']['rms_mean']:.4f}g\n"
                        f"- Z轴 RMS: {stats_a['z']['rms_mean']:.4f}g\n"
                        f"- X轴主频: {stats_a['x']['freq_mean']:.0f}Hz\n\n"
                        f"{machine_b}机床{process_cn}（{process}）振动特征：\n"
                        f"- X轴 RMS: {stats_b['x']['rms_mean']:.4f}g\n"
                        f"- Y轴 RMS: {stats_b['y']['rms_mean']:.4f}g\n"
                        f"- Z轴 RMS: {stats_b['z']['rms_mean']:.4f}g\n"
                        f"- X轴主频: {stats_b['x']['freq_mean']:.0f}Hz"
                    )
                    output_text = self._generate_comparison_output(
                        machine_a, machine_b, process, process_cn, stats_a, stats_b
                    )

                    samples.append({
                        "instruction": instruction,
                        "input": input_text,
                        "output": output_text,
                        "source": {
                            "machine": f"{machine_a},{machine_b}",
                            "process": process,
                            "timeframe": "aggregated",
                            "label": "comparison",
                        },
                        "category": "comparison",
                    })

        return samples

    def _generate_maintenance_output(
        self, machine: str, process: str, process_cn: str,
        good_stats: dict, bad_stats: dict, trend_direction: str
    ) -> str:
        if trend_direction == "increasing":
            trend_desc = "振动幅值呈上升趋势"
            urgency = "高"
            priority = "优先"
        elif trend_direction == "stable_high":
            trend_desc = "振动幅值持续处于较高水平"
            urgency = "中"
            priority = "建议"
        else:
            trend_desc = "振动幅值相对稳定"
            urgency = "低"
            priority = "可延后"

        rms_avg = (good_stats['x']['rms_mean'] + good_stats['y']['rms_mean'] + good_stats['z']['rms_mean']) / 3
        bad_rms_avg = (bad_stats['x']['rms_mean'] + bad_stats['y']['rms_mean'] + bad_stats['z']['rms_mean']) / 3
        degradation_ratio = bad_rms_avg / max(rms_avg, 1e-10)

        output = (
            f"趋势分析：\n"
            f"1. {machine}机床{process_cn}工序近 6 个月振动数据显示：{trend_desc}\n"
            f"2. 当前平均 RMS 值 {bad_rms_avg:.4f}g，较正常基线 {rms_avg:.4f}g 升高 {degradation_ratio:.1f} 倍\n"
            f"3. 主频分布出现偏移，表明主轴负载增大\n\n"
            f"退化评估：\n"
            f"1. 设备健康度：{'较差' if degradation_ratio > 3.0 else '一般' if degradation_ratio > 2.0 else '良好'}\n"
            f"2. 退化速率：{'快速' if degradation_ratio > 3.0 else '中等' if degradation_ratio > 2.0 else '缓慢'}\n"
            f"3. 预计剩余使用寿命：{'1~2 个月' if degradation_ratio > 3.0 else '3~6 个月' if degradation_ratio > 2.0 else '6 个月以上'}\n\n"
            f"维护建议和优先级：\n"
            f"1. 优先级：{priority}安排维护\n"
            f"2. 紧急程度：{urgency}\n"
            f"3. 具体措施：\n"
            f"   - 检查主轴轴承状态，测量径向跳动\n"
            f"   - 检测导轨和丝杠磨损情况\n"
            f"   - 检查润滑系统，更换润滑油\n"
            f"   - 校准机床几何精度\n"
            f"4. 建议在下次维护后重新建立振动基线"
        )
        return output

    def generate_preventive_maintenance_samples(self) -> list[dict]:
        """生成预防性维护类微调样本"""
        samples = []
        process_features = self._get_process_features()

        machines = set()
        for key, data in process_features.items():
            machines.add(data["machine"])

        for machine in machines:
            machine_data = {k: v for k, v in process_features.items() if v["machine"] == machine}

            if not machine_data:
                continue

            all_good_feats = []
            all_bad_feats = []
            for data in machine_data.values():
                all_good_feats.extend(data["good_feats"])
                all_bad_feats.extend(data["bad_feats"])

            if not all_good_feats:
                continue

            good_stats = {
                axis: self._compute_axis_stats(all_good_feats, axis)
                for axis in ["x", "y", "z"]
            }

            if all_bad_feats:
                bad_stats = {
                    axis: self._compute_axis_stats(all_bad_feats, axis)
                    for axis in ["x", "y", "z"]
                }
            else:
                bad_stats = good_stats

            for process, data in machine_data.items():
                if not data["bad_feats"]:
                    continue

                process_cn = data["process_cn"]
                months = random.choice([3, 6, 12])
                trend = random.choice(["increasing", "stable_high", "increasing"])

                instruction = random.choice(MAINTENANCE_INSTRUCTIONS).format(
                    months=months, machine=machine, process=process, process_cn=process_cn
                )
                input_text = (
                    f"机床：{machine}\n"
                    f"监测工序：{process}（{process_cn}）\n"
                    f"监测周期：{months}个月\n"
                    f"当前振动特征：\n"
                    f"- X轴 RMS: {bad_stats['x']['rms_mean']:.4f}g\n"
                    f"- Y轴 RMS: {bad_stats['y']['rms_mean']:.4f}g\n"
                    f"- Z轴 RMS: {bad_stats['z']['rms_mean']:.4f}g\n"
                    f"- 正常基线 RMS: {good_stats['x']['rms_mean']:.4f}g / {good_stats['y']['rms_mean']:.4f}g / {good_stats['z']['rms_mean']:.4f}g"
                )
                output_text = self._generate_maintenance_output(
                    machine, process, process_cn, good_stats, bad_stats, trend
                )

                samples.append({
                    "instruction": instruction,
                    "input": input_text,
                    "output": output_text,
                    "source": {
                        "machine": machine,
                        "process": process,
                        "timeframe": f"{months}_months",
                        "label": "maintenance",
                    },
                    "category": "maintenance",
                })

        return samples

    def build_all_datasets(
        self,
        output_dir: str = "python/app/data/datasets/bosch_finetune",
        train_ratio: float = 0.8,
    ) -> dict:
        """构建全部微调数据集并保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        all_samples: list[dict] = []

        diagnosis_samples = self.generate_diagnosis_samples()
        all_samples.extend(diagnosis_samples)

        param_opt_samples = self.generate_parameter_optimization_samples()
        all_samples.extend(param_opt_samples)

        comparison_samples = self.generate_comparison_samples()
        all_samples.extend(comparison_samples)

        maintenance_samples = self.generate_preventive_maintenance_samples()
        all_samples.extend(maintenance_samples)

        random.shuffle(all_samples)
        split_idx = int(len(all_samples) * train_ratio)
        train_samples = all_samples[:split_idx]
        val_samples = all_samples[split_idx:]

        def write_jsonl(samples: list[dict], filepath: Path):
            with open(filepath, "w", encoding="utf-8") as f:
                for sample in samples:
                    f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        write_jsonl(train_samples, output_path / "train.jsonl")
        write_jsonl(val_samples, output_path / "val.jsonl")

        category_counts = {}
        for sample in all_samples:
            cat = sample.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        dataset_info = {
            "total_samples": len(all_samples),
            "train_samples": len(train_samples),
            "val_samples": len(val_samples),
            "categories": category_counts,
            "created_at": datetime.now().isoformat(),
            "data_dir": self.data_dir,
            "train_ratio": train_ratio,
        }

        with open(output_path / "dataset_info.json", "w", encoding="utf-8") as f:
            json.dump(dataset_info, f, ensure_ascii=False, indent=2)

        return dataset_info

    def export_for_ollama(
        self,
        output_path: str = "python/app/data/datasets/bosch_finetune/ollama_format.jsonl",
    ) -> str:
        """导出为 Ollama 兼容的微调格式"""
        output_p = Path(output_path)
        output_p.parent.mkdir(parents=True, exist_ok=True)

        all_samples: list[dict] = []
        all_samples.extend(self.generate_diagnosis_samples())
        all_samples.extend(self.generate_parameter_optimization_samples())
        all_samples.extend(self.generate_comparison_samples())
        all_samples.extend(self.generate_preventive_maintenance_samples())

        ollama_samples = []
        for sample in all_samples:
            ollama_sample = {
                "messages": [
                    {"role": "user", "content": sample["instruction"] + "\n\n" + sample["input"]},
                    {"role": "assistant", "content": sample["output"]},
                ],
                "source": sample.get("source", {}),
                "category": sample.get("category", "unknown"),
            }
            ollama_samples.append(ollama_sample)

        with open(output_p, "w", encoding="utf-8") as f:
            for sample in ollama_samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        return str(output_p)
