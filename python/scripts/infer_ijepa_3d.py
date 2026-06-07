"""I-JEPA 3D推理入口脚本。

用法:
    python scripts/infer_ijepa_3d.py --model ./checkpoints/final_model.pth \
        --front front.png --side side.png --top top.png --output result.json

可选参数:
    --model: 模型检查点路径
    --front: 正视视图图像路径
    --side: 侧视视图图像路径
    --top: 俯视视图图像路径
    --output: 输出JSON路径
    --device: 计算设备 (cuda/cpu)
    --batch_dir: 批量推理目录
"""

import sys
import os
import argparse
import json
import logging
from typing import Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import torch  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai.ijepa_3d.config import IJEPA3DConfig  # noqa: E402
from app.ai.ijepa_3d.model import IJEPA3DModel  # noqa: E402
from app.ai.ijepa_3d.inference import IJEPA3DInference  # noqa: E402


def setup_logging() -> None:
    """配置日志。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


def load_image(image_path: str, image_size: int = 256) -> torch.Tensor:
    """加载并预处理图像。

    Args:
        image_path: 图像路径
        image_size: 目标尺寸

    Returns:
        归一化图像张量 (1, 3, 256, 256)
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    img = Image.open(image_path).convert("RGB")
    img = img.resize((image_size, image_size), Image.BILINEAR)
    img_array = np.array(img, dtype=np.float32) / 255.0
    return torch.from_numpy(img_array).permute(2, 0, 1).unsqueeze(0)


def load_model(
    checkpoint_path: str,
    device: str = "cuda",
) -> IJEPA3DModel:
    """加载训练好的模型。

    Args:
        checkpoint_path: 检查点路径
        device: 计算设备

    Returns:
        加载的模型
    """
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"Checkpoint not found: {checkpoint_path}"
        )

    checkpoint = torch.load(checkpoint_path, map_location=device)

    # 从检查点恢复配置
    if "config" in checkpoint:
        config = checkpoint["config"]
    else:
        logging.warning("Config not found in checkpoint, using default")
        config = IJEPA3DConfig()

    model = IJEPA3DModel(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    logging.info(f"Model loaded from {checkpoint_path}")
    return model


def format_output(
    bbox: np.ndarray,
    keypoints: np.ndarray,
    view_weights: np.ndarray,
    relations: Optional[Dict] = None,
    inference_time_ms: float = 0.0,
) -> dict:
    """格式化推理输出为JSON友好格式。

    Args:
        bbox: 边界框 (6,)
        keypoints: 关键点 (10, 3)
        view_weights: 视图权重 (3,)
        relations: 拓扑关系
        inference_time_ms: 推理耗时

    Returns:
        格式化的输出字典
    """
    result = {
        "bbox_3d": {
            "center_x_mm": float(bbox[0]),
            "center_y_mm": float(bbox[1]),
            "center_z_mm": float(bbox[2]),
            "length_mm": float(bbox[3]),
            "width_mm": float(bbox[4]),
            "height_mm": float(bbox[5]),
        },
        "keypoints": [
            {
                "id": i,
                "x_mm": float(keypoints[i, 0]),
                "y_mm": float(keypoints[i, 1]),
                "z_mm": float(keypoints[i, 2]),
            }
            for i in range(keypoints.shape[0])
        ],
        "view_weights": {
            "front": float(view_weights[0]),
            "side": float(view_weights[1]),
            "top": float(view_weights[2]),
        },
        "inference_time_ms": round(inference_time_ms, 2),
    }

    if relations:
        result["topology"] = relations

    return result


def infer_single(
    engine: IJEPA3DInference,
    front_path: str,
    side_path: str,
    top_path: str,
    output_path: Optional[str] = None,
    analyze_topology: bool = True,
) -> dict:
    """单样本推理。

    Args:
        engine: 推理引擎
        front_path: 正视视图路径
        side_path: 侧视视图路径
        top_path: 俯视视图路径
        output_path: 输出JSON路径
        analyze_topology: 是否分析拓扑关系

    Returns:
        推理结果字典
    """
    logging.info("Loading images...")
    front = load_image(front_path)
    side = load_image(side_path)
    top = load_image(top_path)

    logging.info("Running inference...")
    result = engine.infer_single(front, side, top)

    bbox = result["bbox"]
    keypoints = result["keypoints"]
    weights = result["view_weights"]
    inf_time = result["inference_time_ms"]

    # 后处理
    postprocessed = engine.postprocess_results(
        bbox.reshape(1, -1), keypoints.reshape(1, 10, 3),
    )

    relations = None
    if analyze_topology:
        relations = engine.get_feature_relations(keypoints, bbox)

    # 格式化输出
    output = format_output(
        postprocessed["bbox"][0],
        postprocessed["keypoints"][0],
        weights,
        relations,
        inf_time,
    )

    # 打印结果
    logging.info("=" * 40)
    logging.info("Inference Results:")
    logging.info(f"  BBox: {output['bbox_3d']}")
    logging.info(f"  View Weights: {output['view_weights']}")
    logging.info(f"  Inference Time: {inf_time:.2f}ms")
    logging.info(f"  Keypoints: {len(output['keypoints'])} points detected")
    if relations:
        logging.info(
            f"  Topology: {len(relations['same_plane'])} same-plane pairs"
        )
    logging.info("=" * 40)

    # 保存输出
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        logging.info(f"Results saved to {output_path}")

    return output


def infer_batch_directory(
    engine: IJEPA3DInference,
    batch_dir: str,
    output_dir: str,
) -> None:
    """批量推理目录中的所有三视图组。

    期望目录结构：
    batch_dir/
      001_front.png  001_side.png  001_top.png
      002_front.png  002_side.png  002_top.png
      ...

    Args:
        engine: 推理引擎
        batch_dir: 输入目录
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)

    # 查找所有正视视图
    import glob
    front_files = sorted(glob.glob(os.path.join(batch_dir, "*_front.png")))

    if not front_files:
        logging.warning(f"No *_front.png files found in {batch_dir}")
        return

    logging.info(f"Found {len(front_files)} samples in {batch_dir}")

    results = []
    total_time = 0.0

    for front_path in front_files:
        # 推断对应视图路径
        base = front_path.replace("_front.png", "")
        sample_id = os.path.basename(base)
        side_path = f"{base}_side.png"
        top_path = f"{base}_top.png"

        if not os.path.exists(side_path) or not os.path.exists(top_path):
            logging.warning(
                f"Missing views for {sample_id}, skipping"
            )
            continue

        try:
            output = infer_single(
                engine, front_path, side_path, top_path,
                analyze_topology=False,
            )
            output["sample_id"] = sample_id
            results.append(output)
            total_time += output["inference_time_ms"]
        except Exception as e:
            logging.error(f"Failed to infer {sample_id}: {e}")

    # 保存批量结果
    batch_output = {
        "num_samples": len(results),
        "total_time_ms": round(total_time, 2),
        "avg_time_ms": round(total_time / max(1, len(results)), 2),
        "results": results,
    }

    output_path = os.path.join(output_dir, "batch_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(batch_output, f, indent=2, ensure_ascii=False)

    logging.info(
        f"Batch inference complete: {len(results)} samples, "
        f"avg {batch_output['avg_time_ms']}ms/sample"
    )
    logging.info(f"Results saved to {output_path}")


def main():
    """主推理入口。"""
    parser = argparse.ArgumentParser(
        description="I-JEPA 3D Geometry Extraction Inference",
    )
    parser.add_argument(
        "--model", type=str, required=True,
        help="Path to model checkpoint",
    )
    parser.add_argument(
        "--front", type=str, default=None,
        help="Front view image path",
    )
    parser.add_argument(
        "--side", type=str, default=None,
        help="Side view image path",
    )
    parser.add_argument(
        "--top", type=str, default=None,
        help="Top view image path",
    )
    parser.add_argument(
        "--output", type=str, default="./output/inference_result.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--device", type=str, default="cuda",
        help="Compute device (cuda/cpu)",
    )
    parser.add_argument(
        "--batch_dir", type=str, default=None,
        help="Batch inference directory",
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Run inference benchmark",
    )

    args = parser.parse_args()
    setup_logging()

    logger = logging.getLogger(__name__)

    # 检测设备
    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU")
        args.device = "cpu"

    # 加载模型
    model = load_model(args.model, args.device)
    engine = IJEPA3DInference(model, device=args.device)

    # 性能基准测试
    if args.benchmark:
        logger.info("Running inference benchmark...")
        results = engine.benchmark_inference(num_samples=50)
        for key, val in results.items():
            logger.info(f"  {key}: {val}")
        return

    # 批量推理
    if args.batch_dir:
        output_dir = os.path.join(
            os.path.dirname(args.output),
            "batch_output",
        )
        infer_batch_directory(engine, args.batch_dir, output_dir)
        return

    # 单样本推理
    if args.front and args.side and args.top:
        infer_single(
            engine, args.front, args.side, args.top, args.output,
        )
    else:
        logger.error(
            "Please provide either --front/--side/--top for single inference "
            "or --batch_dir for batch inference"
        )
        parser.print_help()


if __name__ == "__main__":
    main()
