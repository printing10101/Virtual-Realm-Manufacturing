"""I-JEPA 3D训练入口脚本。

用法:
    python scripts/train_ijepa_3d.py --data_dir ./data/ijepa_3d/ --output_dir ./checkpoints/

可选参数:
    --data_dir: 数据集目录路径
    --output_dir: 检查点保存目录
    --device: 计算设备 (cuda/cpu)
    --stage1_epochs: 阶段一训练轮数
    --stage2_epochs: 阶段二训练轮数
    --batch_size: 批次大小
    --lr: 学习率
    --resume: 从检查点恢复训练
"""

import sys
import os
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import torch  # noqa: E402
from app.ai.ijepa_3d.config import IJEPA3DConfig  # noqa: E402
from app.ai.ijepa_3d.model import IJEPA3DModel  # noqa: E402
from app.ai.ijepa_3d.dataset import IJEPA3DDataset  # noqa: E402
from app.ai.ijepa_3d.trainer import IJEPA3DTrainer  # noqa: E402


def setup_logging(output_dir: str) -> None:
    """配置日志系统。

    Args:
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)

    log_file = os.path.join(
        output_dir,
        f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    )

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def prepare_data(
    data_dir: str,
    batch_size: int = 32,
    num_workers: int = 4,
) -> tuple:
    """准备训练和验证数据加载器。

    如果标注文件不存在，自动生成虚拟标注数据用于开发测试。

    Args:
        data_dir: 数据目录
        batch_size: 批次大小
        num_workers: 数据加载线程数

    Returns:
        (train_loader, val_loader)
    """
    annotations_path = os.path.join(data_dir, "annotations.json")
    images_dir = os.path.join(data_dir, "images")

    # 确保目录存在
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(images_dir, exist_ok=True)

    # 如果没有标注文件，生成虚拟数据
    if not os.path.exists(annotations_path):
        logging.warning(
            f"Annotations not found at {annotations_path}, "
            "generating dummy data..."
        )
        IJEPA3DDataset.generate_dummy_annotations(
            annotations_path, num_samples=500,
        )

    # 创建数据集
    train_dataset = IJEPA3DDataset(
        data_dir=data_dir,
        split="train",
        augment=True,
    )
    val_dataset = IJEPA3DDataset(
        data_dir=data_dir,
        split="val",
        augment=False,
    )

    # 创建数据加载器
    train_loader = train_dataset.get_dataloader(
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
    )
    val_loader = val_dataset.get_dataloader(
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
    )

    logging.info(
        f"Data prepared: {len(train_dataset)} train, "
        f"{len(val_dataset)} val samples"
    )

    # 打印类型分布
    dist = train_dataset.get_part_type_distribution()
    logging.info(f"Part type distribution: {dist}")

    return train_loader, val_loader


def main():
    """主训练入口。"""
    parser = argparse.ArgumentParser(
        description="I-JEPA 3D Geometry Extraction Training",
    )
    parser.add_argument(
        "--data_dir", type=str, default="./data/ijepa_3d/",
        help="Dataset directory",
    )
    parser.add_argument(
        "--output_dir", type=str, default="./checkpoints/ijepa_3d/",
        help="Output directory for checkpoints",
    )
    parser.add_argument(
        "--device", type=str, default="cuda",
        help="Compute device (cuda/cpu)",
    )
    parser.add_argument(
        "--stage1_epochs", type=int, default=None,
        help="Stage 1 epochs (default from config)",
    )
    parser.add_argument(
        "--stage2_epochs", type=int, default=None,
        help="Stage 2 epochs (default from config)",
    )
    parser.add_argument(
        "--batch_size", type=int, default=None,
        help="Batch size (default from config)",
    )
    parser.add_argument(
        "--lr", type=float, default=None,
        help="Learning rate (default from config)",
    )
    parser.add_argument(
        "--resume", type=str, default=None,
        help="Resume from checkpoint path",
    )
    parser.add_argument(
        "--num_workers", type=int, default=4,
        help="Number of data loading workers",
    )
    parser.add_argument(
        "--no_amp", action="store_true",
        help="Disable automatic mixed precision",
    )

    args = parser.parse_args()

    # 设置日志
    setup_logging(args.output_dir)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("I-JEPA 3D Training Script")
    logger.info(f"Arguments: {args}")
    logger.info("=" * 60)

    # 创建配置
    config = IJEPA3DConfig()

    if args.stage1_epochs is not None:
        config.stage1_epochs = args.stage1_epochs
    if args.stage2_epochs is not None:
        config.stage2_epochs = args.stage2_epochs
    if args.batch_size is not None:
        config.stage1_batch_size = args.batch_size
        config.stage2_batch_size = args.batch_size
    if args.lr is not None:
        config.stage1_lr = args.lr
        config.stage2_lr = args.lr * 0.2

    logger.info(f"Config: {config}")

    # 准备数据
    batch_size = config.stage1_batch_size
    train_loader, val_loader = prepare_data(
        args.data_dir, batch_size, args.num_workers,
    )

    # 检测设备
    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU")
        args.device = "cpu"

    # 创建模型
    model = IJEPA3DModel(config)

    # 加载检查点（如果指定）
    if args.resume:
        logger.info(f"Resuming from checkpoint: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=args.device)
        model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(
            f"Loaded checkpoint from epoch {checkpoint.get('epoch', 'unknown')}"
        )

    # 打印模型信息
    param_counts = model.count_parameters()
    logger.info(f"Model parameters: {param_counts}")

    # 创建训练器
    trainer = IJEPA3DTrainer(
        model=model,
        config=config,
        device=args.device,
        output_dir=args.output_dir,
        use_amp=not args.no_amp,
    )

    # 开始训练
    logger.info("Starting training...")
    try:
        results = trainer.train(train_loader, val_loader)
        logger.info(f"Training completed: {results}")
    except KeyboardInterrupt:
        logger.info("Training interrupted by user")
        trainer.save_checkpoint("interrupted.pth", trainer.current_stage, trainer.current_epoch, {})
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise

    # 保存最终模型
    final_path = os.path.join(args.output_dir, "final_model.pth")
    torch.save({
        "model_state_dict": model.state_dict(),
        "config": config,
    }, final_path)
    logger.info(f"Final model saved to {final_path}")

    logger.info("Training script completed successfully!")


if __name__ == "__main__":
    main()
