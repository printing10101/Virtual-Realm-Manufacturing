import logging
import uuid
from typing import Callable

import numpy as np

from app.data.bosch_cnc_loader import BoschCNCDataLoader
from app.rag.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

PROCESS_NAMES = {
    "OP00": "端面铣削", "OP01": "粗铣外轮廓", "OP02": "精铣外轮廓",
    "OP03": "钻孔", "OP04": "扩孔/铰孔", "OP05": "粗镗孔",
    "OP06": "精镗孔", "OP07": "铣槽", "OP08": "铣台阶面",
    "OP09": "粗铣内腔", "OP10": "精铣内腔", "OP11": "倒角",
    "OP12": "攻丝", "OP13": "去毛刺", "OP14": "最终检验",
}

SEVERITY_MAP = {1: "轻度异常", 2: "中度异常", 3: "重度异常"}


class BoschKnowledgeBuilder:
    """从 Bosch CNC 数据集自动构建工艺振动知识条目"""

    def __init__(self, data_dir: str, knowledge_base: KnowledgeBase):
        self.data_dir = data_dir
        self.kb = knowledge_base
        self.loader = BoschCNCDataLoader(data_dir=data_dir)
        self._progress_callback: Callable[[str, int, int], None] | None = None

    def set_progress_callback(self, callback: Callable[[str, int, int], None]):
        self._progress_callback = callback

    def _notify(self, stage: str, current: int, total: int):
        if self._progress_callback:
            self._progress_callback(stage, current, total)

    def build_process_knowledge(self) -> list[str]:
        summary = self.loader.get_dataset_summary()
        processes = summary.get("available_processes", [])
        machines = summary.get("available_machines", [])
        all_ids: list[str] = []

        total = len(processes) * len(machines)
        idx = 0

        for machine in machines:
            for process in processes:
                idx += 1
                self._notify("process_knowledge", idx, total)

                good_samples = self.loader.load_dataset(
                    machines=[machine], processes=[process], labels=["good"]
                )
                bad_samples = self.loader.load_dataset(
                    machines=[machine], processes=[process], labels=["bad"]
                )

                if not good_samples and not bad_samples:
                    continue

                good_feats = [self.loader.extract_features(s["data"]) for s in good_samples]
                bad_feats = [self.loader.extract_features(s["data"]) for s in bad_samples]

                entry = self._build_process_entry(
                    machine=machine,
                    process=process,
                    good_feats=good_feats,
                    bad_feats=bad_feats,
                    good_count=len(good_samples),
                    bad_count=len(bad_samples),
                )
                if entry:
                    doc_id = f"bosch_process_{machine}_{process}"
                    try:
                        self.kb.add_knowledge(
                            document=entry["document"],
                            metadata=entry["metadata"],
                            doc_id=doc_id
                        )
                        all_ids.append(doc_id)
                    except Exception:
                        alt_id = f"{doc_id}_{uuid.uuid4().hex[:8]}"
                        self.kb.add_knowledge(
                            document=entry["document"],
                            metadata=entry["metadata"],
                            doc_id=alt_id
                        )
                        all_ids.append(alt_id)

        logger.info("Built process knowledge: %d entries", len(all_ids))
        return all_ids

    def _build_process_entry(
        self, machine: str, process: str,
        good_feats: list[dict], bad_feats: list[dict],
        good_count: int, bad_count: int,
    ) -> dict | None:
        process_cn = PROCESS_NAMES.get(process, process)
        total_samples = good_count + bad_count

        if total_samples == 0:
            return None

        lines: list[str] = []
        lines.append(f"【工序振动特征】{process_cn} {process}")
        lines.append(f"机床：{machine}（正常样本：{good_count}，异常样本：{bad_count}）")
        lines.append("")

        if good_feats:
            lines.append("正常状态振动特征：")
            for ax in ["x", "y", "z"]:
                axis_feat = self._axis_stats(good_feats, ax)
                lines.append(
                    f"- {ax.upper()}轴 RMS：{axis_feat['rms_min']:.4f}~{axis_feat['rms_max']:.4f}g"
                    f"（均值 {axis_feat['rms_mean']:.4f}g）"
                )
            lines.append(
                f"- 主频范围：{self._freq_range(good_feats):.0f}~"
                f"{self._freq_range(good_feats, use_max=True):.0f}Hz"
            )
            energy = self._energy_distribution(good_feats)
            lines.append(
                f"- 能量分布：X轴 {energy['x']:.0f}%，Y轴 {energy['y']:.0f}%，"
                f"Z轴 {energy['z']:.0f}%"
            )
            lines.append("")

        if bad_feats and good_feats:
            lines.append("异常状态特征变化：")
            ratios = self._compute_ratio(good_feats, bad_feats)
            lines.append(f"- 振动幅值增大 {ratios['rms_min']:.1f}~{ratios['rms_max']:.1f} 倍")
            lines.append(f"- 主频偏移超过 {ratios['freq_shift']:.0f}%")
            energy_shifts = ratios.get("energy_shifts", {})
            max_shift_ax = max(energy_shifts, key=energy_shifts.get, default="x")
            lines.append(f"- {max_shift_ax.upper()}轴能量占比显著增加")
            lines.append("")
            lines.append("异常严重程度分级：")
            if ratios['rms_max'] <= 2.0:
                lines.append("- 轻度异常：振动幅值略高于正常，建议加强监测")
            elif ratios['rms_max'] <= 4.0:
                lines.append("- 中度异常：振动幅值明显增大，建议近期更换刀具")
            else:
                lines.append("- 重度异常：振动幅值严重超标，须立即停机检查")
            lines.append("")

        lines.append("工艺建议：")
        lines.append("- 振动幅值超过正常基线 2.5 倍时建议检查刀具状态")
        lines.append("- 主频偏移超过 20% 时建议检查主轴轴承")
        lines.append("- 建议每加工 50~100 件后使用振动监测进行状态评估")
        lines.append(f"- 工序 {process} 建议参考 {machine} 的历史振动基线进行异常判断")

        return {
            "document": "\n".join(lines),
            "metadata": {
                "source": "bosch_cnc",
                "type": "process_vibration_signature",
                "process": process,
                "process_name": process_cn,
                "machine": machine,
                "category": "process_monitoring",
                "good_samples": good_count,
                "bad_samples": bad_count,
                "keywords": f"Bosch CNC,{process},{process_cn},{machine},振动特征,RMS,主频,能量分布",
            }
        }

    def _axis_stats(self, feats: list[dict], axis: str) -> dict:
        rms_vals = [f.get(f"time_{axis}_rms", 0) for f in feats]
        rms_vals = [v for v in rms_vals if np.isfinite(v)]
        if not rms_vals:
            return {"rms_min": 0, "rms_max": 0, "rms_mean": 0}
        arr = np.array(rms_vals)
        return {
            "rms_min": float(np.min(arr)),
            "rms_max": float(np.max(arr)),
            "rms_mean": float(np.mean(arr)),
        }

    def _freq_range(self, feats: list[dict], use_max: bool = False) -> float:
        dom_freqs: list[float] = []
        for f in feats:
            for ax in ["x", "y", "z"]:
                v = f.get(f"freq_{ax}_dominant_freq", 0)
                if np.isfinite(v):
                    dom_freqs.append(v)
        if not dom_freqs:
            return 0.0
        arr = np.array(dom_freqs)
        return float(np.max(arr)) if use_max else float(np.min(arr))

    def _energy_distribution(self, feats: list[dict]) -> dict:
        energies = {"x": [], "y": [], "z": []}
        for f in feats:
            for ax in ["x", "y", "z"]:
                v = f.get(f"cross_{ax}_energy_ratio", 0)
                if np.isfinite(v):
                    energies[ax].append(v)
        result = {}
        for ax in ["x", "y", "z"]:
            vals = energies[ax]
            result[ax] = float(np.mean(vals)) * 100 if vals else 0.0
        return result

    def _compute_ratio(self, good_feats: list[dict], bad_feats: list[dict]) -> dict:
        good_rms = []
        bad_rms = []
        good_freq = []
        bad_freq = []
        good_energy = {"x": [], "y": [], "z": []}
        bad_energy = {"x": [], "y": [], "z": []}

        for feats in good_feats:
            for ax in ["x", "y", "z"]:
                good_rms.append(feats.get(f"time_{ax}_rms", 0))
                good_freq.append(feats.get(f"freq_{ax}_dominant_freq", 0))
                good_energy[ax].append(feats.get(f"cross_{ax}_energy_ratio", 0))
        for feats in bad_feats:
            for ax in ["x", "y", "z"]:
                bad_rms.append(feats.get(f"time_{ax}_rms", 0))
                bad_freq.append(feats.get(f"freq_{ax}_dominant_freq", 0))
                bad_energy[ax].append(feats.get(f"cross_{ax}_energy_ratio", 0))

        g_mean = float(np.mean(good_rms)) if good_rms else 1.0
        b_mean = float(np.mean(bad_rms)) if bad_rms else 1.0
        rms_min = b_mean / max(g_mean, 1e-10) if g_mean > 0 else 1.0
        rms_max = (b_mean + float(np.std(bad_rms))) / max(g_mean, 1e-10) if bad_rms and g_mean > 0 else 1.0

        g_freq = float(np.mean(good_freq)) if good_freq else 1.0
        b_freq = float(np.mean(bad_freq)) if bad_freq else 1.0
        freq_shift = abs(b_freq - g_freq) / max(g_freq, 1e-10) * 100

        energy_shifts: dict[str, float] = {}
        for ax in ["x", "y", "z"]:
            g_e = float(np.mean(good_energy[ax])) if good_energy[ax] else 0.0
            b_e = float(np.mean(bad_energy[ax])) if bad_energy[ax] else 0.0
            energy_shifts[ax] = abs(b_e - g_e) * 100

        return {
            "rms_min": round(min(rms_min, rms_max), 1),
            "rms_max": round(max(rms_min, rms_max), 1),
            "freq_shift": round(freq_shift, 1),
            "energy_shifts": energy_shifts,
        }

    def build_machine_knowledge(self) -> list[str]:
        summary = self.loader.get_dataset_summary()
        machines = summary.get("available_machines", [])
        all_ids: list[str] = []

        for idx, machine in enumerate(machines):
            self._notify("machine_knowledge", idx + 1, len(machines))

            all_good = self.loader.load_dataset(machines=[machine], labels=["good"])
            all_bad = self.loader.load_dataset(machines=[machine], labels=["bad"])

            good_feats = [self.loader.extract_features(s["data"]) for s in all_good]
            bad_feats = [self.loader.extract_features(s["data"]) for s in all_bad]

            lines: list[str] = []
            lines.append(f"【机床振动特征汇总】{machine}")
            lines.append(f"正常样本数：{len(all_good)}，异常样本数：{len(all_bad)}，合计：{len(all_good) + len(all_bad)}")
            lines.append("")

            if good_feats:
                lines.append("整体正常振动特征：")
                for ax in ["x", "y", "z"]:
                    stats = self._axis_stats(good_feats, ax)
                    lines.append(
                        f"- {ax.upper()}轴 RMS 均值 {stats['rms_mean']:.4f}g"
                        f"（范围 {stats['rms_min']:.4f}~{stats['rms_max']:.4f}g）"
                    )
                lines.append(f"- 全工序主频范围：{self._freq_range(good_feats):.0f}~{self._freq_range(good_feats, use_max=True):.0f}Hz")
                lines.append("")

            if bad_feats:
                lines.append("异常检出率：")
                bad_ratio = len(all_bad) / max(len(all_good) + len(all_bad), 1) * 100
                lines.append(f"- 异常样本占比 {bad_ratio:.1f}%")
                lines.append("")

            lines.append("维护建议：")
            lines.append(f"- 机床 {machine} 应建立专属振动基线库，定期更新")
            lines.append("- 建议安装在线振动监测系统，实现实时状态跟踪")
            lines.append("- 结合振动趋势分析，提前 2~3 个加工周期预警刀具更换")

            doc_id = f"bosch_machine_{machine}"
            try:
                self.kb.add_knowledge(
                    document="\n".join(lines),
                    metadata={
                        "source": "bosch_cnc",
                        "type": "machine_signature",
                        "machine": machine,
                        "category": "machine_health",
                        "good_samples": len(all_good),
                        "bad_samples": len(all_bad),
                        "keywords": f"Bosch CNC,{machine},机床特征,振动基线,状态监测",
                    },
                    doc_id=doc_id
                )
                all_ids.append(doc_id)
            except Exception:
                alt_id = f"{doc_id}_{uuid.uuid4().hex[:8]}"
                self.kb.add_knowledge(
                    document="\n".join(lines),
                    metadata={
                        "source": "bosch_cnc",
                        "type": "machine_signature",
                        "machine": machine,
                        "category": "machine_health",
                        "good_samples": len(all_good),
                        "bad_samples": len(all_bad),
                        "keywords": f"Bosch CNC,{machine},机床特征,振动基线,状态监测",
                    },
                    doc_id=alt_id
                )
                all_ids.append(alt_id)

        logger.info("Built machine knowledge: %d entries", len(all_ids))
        return all_ids

    def build_anomaly_pattern_knowledge(self) -> list[str]:
        summary = self.loader.get_dataset_summary()
        processes = summary.get("available_processes", [])
        machines = summary.get("available_machines", [])
        all_ids: list[str] = []

        anomaly_processes: list[dict] = []
        for machine in machines:
            for process in processes:
                good = self.loader.load_dataset(machines=[machine], processes=[process], labels=["good"])
                bad = self.loader.load_dataset(machines=[machine], processes=[process], labels=["bad"])
                if bad:
                    good_feats = [self.loader.extract_features(s["data"]) for s in good]
                    bad_feats = [self.loader.extract_features(s["data"]) for s in bad]
                    ratios = self._compute_ratio(good_feats, bad_feats) if good_feats else {"rms_max": 1.0}
                    anomaly_processes.append({
                        "machine": machine,
                        "process": process,
                        "bad_count": len(bad),
                        "ratio": ratios["rms_max"],
                    })

        if not anomaly_processes:
            logger.info("No anomaly patterns found (no 'bad' samples)")
            return []

        anomaly_processes.sort(key=lambda x: x["ratio"], reverse=True)

        lines: list[str] = []
        lines.append("【异常振动模式与故障诊断建议】")
        lines.append("基于 Bosch CNC 工业数据集分析，以下为各工序常见的异常振动模式及诊断建议：")
        lines.append("")

        for i, ap in enumerate(anomaly_processes[:10], 1):
            process_cn = PROCESS_NAMES.get(ap["process"], ap["process"])
            severity = 1 if ap["ratio"] <= 2.0 else (2 if ap["ratio"] <= 4.0 else 3)
            severity_cn = SEVERITY_MAP[severity]

            lines.append(f"{i}. {process_cn}（{ap['process']}）- 机床 {ap['machine']}")
            lines.append(f"   异常样本数：{ap['bad_count']}，振动幅值倍数：{ap['ratio']:.1f}x")
            lines.append(f"   严重程度：{severity_cn}")

            if severity >= 3:
                lines.append("   可能原因：刀具严重磨损、主轴轴承损坏、切削参数严重不合理")
                lines.append("   建议措施：立即停机检查刀具和主轴；调整切削参数；更换刀具")
            elif severity >= 2:
                lines.append("   可能原因：刀具中度磨损、切削参数偏大、冷却不充分")
                lines.append("   建议措施：近期更换刀具；适当降低切削速度；检查冷却系统")
            else:
                lines.append("   可能原因：轻微刀具磨损、材料硬度波动")
                lines.append("   建议措施：加强监测频率；检查来料一致性")
            lines.append("")

        lines.append("通用异常模式识别规则：")
        lines.append("- 三轴 RMS 同时升高 → 整体切削力增大，刀具钝化/磨损")
        lines.append("- 单轴 RMS 显著升高 → 该方向切削异常，可能存在刀具偏磨")
        lines.append("- 高频能量占比急剧增加 → 刀具崩刃或颤振")
        lines.append("- 主频向下偏移 → 主轴转速不稳定或负载增大")
        lines.append("- 跨轴相关系数降低 → 振动模式紊乱，刀具状态严重恶化")

        doc_id = "bosch_anomaly_patterns"
        for attempt in range(3):
            try:
                self.kb.add_knowledge(
                    document="\n".join(lines),
                    metadata={
                        "source": "bosch_cnc",
                        "type": "anomaly_pattern",
                        "category": "fault_diagnosis",
                        "analyzed_processes": len(anomaly_processes),
                        "keywords": "Bosch CNC,异常检测,故障诊断,振动模式,刀具磨损,主轴故障",
                    },
                    doc_id=doc_id if attempt == 0 else f"{doc_id}_{attempt}"
                )
                all_ids.append(doc_id if attempt == 0 else f"{doc_id}_{attempt}")
                break
            except Exception:
                pass

        logger.info("Built anomaly pattern knowledge: %d entries", len(all_ids))
        return all_ids

    def build_all(self) -> dict:
        counts = {"process": 0, "machine": 0, "anomaly": 0}

        process_ids = self.build_process_knowledge()
        counts["process"] = len(process_ids)

        machine_ids = self.build_machine_knowledge()
        counts["machine"] = len(machine_ids)

        anomaly_ids = self.build_anomaly_pattern_knowledge()
        counts["anomaly"] = len(anomaly_ids)

        total = sum(counts.values())
        logger.info(
            "Knowledge build complete: %d total entries (process=%d, machine=%d, anomaly=%d)",
            total, counts["process"], counts["machine"], counts["anomaly"]
        )

        return {
            "total_entries": total,
            "by_type": counts,
        }
