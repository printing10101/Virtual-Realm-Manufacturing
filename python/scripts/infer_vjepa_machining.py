"""V-JEPA加工异常检测推理入口脚本。

用法:
    python scripts/infer_vjepa_machining.py --model ./checkpoints/final_model.pth \
        --video test.mp4 --output result.json

可选参数:
    --model: 模型检查点路径
    --video: 视频文件路径
    --output: 输出JSON路径
    --device: 计算设备 (cuda/cpu)
    --action_id: 动作类型 (0=刀具移动, 1=换刀, 2=暂停)
    --benchmark: 运行推理性能基准测试
    --max_frames: 最大处理帧数
"""

import sys
import os
import argparse
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch  # noqa: E402

from app.ai.vjepa_machining.config import VJEPAMachiningConfig  # noqa: E402
from app.ai.vjepa_machining.model import VJEPAMachiningModel  # noqa: E402
from app.ai.vjepa_machining.inference import VJEPAInference  # noqa: E402
from app.ai.vjepa_machining.alert_module import AlertModule  # noqa: E402


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def load_model(checkpoint_path: str, device: str = "cuda") -> VJEPAMachiningModel:
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location=device)
    config = checkpoint.get("config", VJEPAMachiningConfig())
    model = VJEPAMachiningModel(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    logging.info(f"Model loaded from {checkpoint_path}")
    return model


def main():
    parser = argparse.ArgumentParser(description="V-JEPA Machining Anomaly Detection Inference")
    parser.add_argument("--model", type=str, required=True, help="Model checkpoint path")
    parser.add_argument("--video", type=str, default=None, help="Video file path")
    parser.add_argument("--output", type=str, default="./output/vjepa_result.json", help="Output JSON path")
    parser.add_argument("--device", type=str, default="cuda", help="Compute device")
    parser.add_argument("--action_id", type=int, default=0, help="Action type ID")
    parser.add_argument("--benchmark", action="store_true", help="Run inference benchmark")
    parser.add_argument("--max_frames", type=int, default=-1, help="Max frames to process")
    parser.add_argument("--save_alerts", action="store_true", help="Save alert history")

    args = parser.parse_args()
    setup_logging()
    logger = logging.getLogger(__name__)

    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU")
        args.device = "cpu"

    model = load_model(args.model, args.device)
    engine = VJEPAInference(model, device=args.device)
    alert_module = AlertModule()

    if args.benchmark:
        logger.info("Running inference benchmark...")
        results = engine.benchmark(num_samples=100)
        logger.info(f"Benchmark results: {json.dumps(results, indent=2)}")
        return

    if args.video:
        logger.info(f"Processing video: {args.video}")
        results = engine.process_video_file(args.video, args.action_id, args.max_frames)

        # 处理告警
        alerts = []
        for r in results:
            result = alert_module.process_result(r)
            alerts.append(result)

        # 统计
        anomaly_count = sum(1 for a in alerts if a.get("异常类型") != "正常")
        logger.info(f"Processed {len(results)} clips, {anomaly_count} anomalies detected")

        # 输出
        output = {
            "video_path": args.video,
            "total_clips": len(results),
            "anomaly_clips": anomaly_count,
            "anomaly_ratio": round(anomaly_count / max(len(results), 1), 3),
            "alert_summary": alert_module.get_alert_summary(),
            "results": alerts,
            "inference_stats": engine.get_statistics(),
        }

        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logger.info(f"Results saved to {args.output}")

        if args.save_alerts:
            alert_path = args.output.replace(".json", "_alerts.json")
            with open(alert_path, "w", encoding="utf-8") as f:
                json.dump(alert_module.alert_history, f, indent=2, ensure_ascii=False)
            logger.info(f"Alert history saved to {alert_path}")
    else:
        logger.error("Please provide --video for inference or --benchmark for benchmarking")


if __name__ == "__main__":
    main()
