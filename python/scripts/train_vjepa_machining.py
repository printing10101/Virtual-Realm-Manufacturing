"""V-JEPA加工异常检测训练入口脚本。

用法:
    python scripts/train_vjepa_machining.py --data_dir ./data/machining/ --output_dir ./checkpoints/vjepa/

可选参数:
    --data_dir: 数据集目录
    --output_dir: 检查点保存目录
    --device: 计算设备 (cuda/cpu)
    --epochs: 训练轮数
    --batch_size: 批次大小
    --lr: 初始学习率
    --resume: 从检查点恢复训练
"""

import sys
import os
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import torch  # noqa: E402
from app.ai.vjepa_machining.config import VJEPAMachiningConfig  # noqa: E402
from app.ai.vjepa_machining.model import VJEPAMachiningModel  # noqa: E402
from app.ai.vjepa_machining.dataset import MachiningVideoDataset  # noqa: E402
from app.ai.vjepa_machining.trainer import VJEPATrainer  # noqa: E402


def setup_logging(output_dir: str):
    os.makedirs(output_dir, exist_ok=True)
    log_file = os.path.join(output_dir, f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def prepare_data(data_dir: str, batch_size: int, num_workers: int = 4):
    """准备训练和验证数据加载器。"""
    os.makedirs(os.path.join(data_dir, "videos", "normal"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "videos", "anomaly"), exist_ok=True)

    train_dataset = MachiningVideoDataset(data_dir=data_dir, split="train", augment=True)
    val_dataset = MachiningVideoDataset(data_dir=data_dir, split="val", augment=False)

    train_loader = train_dataset.get_dataloader(batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = val_dataset.get_dataloader(batch_size=batch_size, shuffle=False, num_workers=num_workers)

    logging.info(f"Data prepared: {len(train_dataset)} train clips, {len(val_dataset)} val clips")
    return train_loader, val_loader


def main():
    parser = argparse.ArgumentParser(description="V-JEPA Machining Anomaly Detection Training")
    parser.add_argument("--data_dir", type=str, default="./data/machining/", help="Dataset directory")
    parser.add_argument("--output_dir", type=str, default="./checkpoints/vjepa_machining/", help="Output directory")
    parser.add_argument("--device", type=str, default="cuda", help="Compute device (cuda/cpu)")
    parser.add_argument("--epochs", type=int, default=None, help="Training epochs")
    parser.add_argument("--batch_size", type=int, default=None, help="Batch size")
    parser.add_argument("--lr", type=float, default=None, help="Initial learning rate")
    parser.add_argument("--resume", type=str, default=None, help="Resume from checkpoint")
    parser.add_argument("--num_workers", type=int, default=4, help="Data loading workers")
    parser.add_argument("--no_amp", action="store_true", help="Disable AMP")

    args = parser.parse_args()
    setup_logging(args.output_dir)

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("V-JEPA Machining Training Script")
    logger.info(f"Arguments: {args}")
    logger.info("=" * 60)

    config = VJEPAMachiningConfig()
    if args.epochs is not None:
        config.epochs = args.epochs
    if args.batch_size is not None:
        config.batch_size = args.batch_size
    if args.lr is not None:
        config.initial_lr = args.lr

    logger.info(f"Config: embed_dim={config.vit_embed_dim}, epochs={config.epochs}, "
                f"batch_size={config.batch_size}, lr={config.initial_lr}")

    train_loader, val_loader = prepare_data(args.data_dir, config.batch_size, args.num_workers)

    if args.device == "cuda" and not torch.cuda.is_available():
        logger.warning("CUDA not available, falling back to CPU")
        args.device = "cpu"

    model = VJEPAMachiningModel(config)

    if args.resume:
        logger.info(f"Resuming from checkpoint: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=args.device)
        model.load_state_dict(checkpoint["model_state_dict"])

    param_counts = model.count_parameters()
    logger.info(f"Model parameters: {param_counts}")

    trainer = VJEPATrainer(
        model=model, config=config, device=args.device,
        output_dir=args.output_dir, use_amp=not args.no_amp,
    )

    logger.info("Starting training...")
    try:
        results = trainer.train(train_loader, val_loader)
        logger.info(f"Training completed. Best F1: {results['best_val_f1']:.4f}")
    except KeyboardInterrupt:
        logger.info("Training interrupted by user")
        trainer.save_checkpoint("interrupted.pth", trainer.current_epoch, {})
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        raise

    final_path = os.path.join(args.output_dir, "final_model.pth")
    torch.save({"model_state_dict": model.state_dict(), "config": config}, final_path)
    logger.info(f"Final model saved to {final_path}")


if __name__ == "__main__":
    main()
