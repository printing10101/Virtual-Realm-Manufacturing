"""
Trainer module for LNN models.

Implements training loop with optimizer, loss function configuration,
mixed precision training, and GPU acceleration support.
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Any, Dict, List, Optional, Tuple, Union
import time
import os
import asyncio
import logging
from datetime import datetime

from app.ai.lnn.training.device_manager import (
    check_gpu_memory_safe,
    clear_gpu_memory,
)

logger = logging.getLogger(__name__)


class LNNTrainer:
    """
    LNN训练器

    包含：
    - 优化器配置
    - 损失函数选择
    - 训练循环
    - 检查点管理
    - 早停机制
    - 梯度裁剪
    - 学习率调度
    - 混合精度训练 (AMP)
    - GPU内存监控
    """

    def __init__(
        self,
        model: nn.Module,
        learning_rate: float = 0.001,
        optimizer_type: str = "adam",
        loss_type: str = "cross_entropy",
        batch_size: int = 32,
        epochs: int = 100,
        early_stopping_patience: int = 5,
        gradient_clip_value: Optional[float] = 1.0,
        lr_scheduler_type: str = "step",
        lr_scheduler_params: Optional[Dict[str, Any]] = None,
        device: Union[str, torch.device] = "cpu",
        use_amp: bool = False,
        progress_callback: Optional[Any] = None,
        cancel_event: Optional[Any] = None,
    ):
        """
        初始化训练器

        Args:
            model: 要训练的LNN模型 (PyTorch nn.Module)
            learning_rate: 学习率
            optimizer_type: 优化器类型 ('sgd', 'adam', 'rmsprop', 'adamw')
            loss_type: 损失函数类型 ('cross_entropy', 'mse', 'mae', 'bce')
            batch_size: 批次大小
            epochs: 训练轮数
            early_stopping_patience: 早停耐心值 (默认5轮)
            gradient_clip_value: 梯度裁剪阈值 (None表示不裁剪)
            lr_scheduler_type: 学习率调度器类型 ('step', 'cosine', 'reduce_on_plateau', 'exponential')
            lr_scheduler_params: 学习率调度器参数
            device: 计算设备 ('cpu', 'cuda', 或 'auto')
            use_amp: 是否启用自动混合精度训练
            progress_callback: 进度回调函数，每个epoch结束后调用
            cancel_event: asyncio.Event 用于接收取消信号
        """
        self.model = model
        self.learning_rate = learning_rate
        self.optimizer_type = optimizer_type
        self.loss_type = loss_type
        self.batch_size = batch_size
        self.epochs = epochs
        self.early_stopping_patience = early_stopping_patience
        self.gradient_clip_value = gradient_clip_value
        self.lr_scheduler_type = lr_scheduler_type
        self.lr_scheduler_params = lr_scheduler_params or {}
        if isinstance(device, str):
            self.device = torch.device(device)
        else:
            self.device = device
        self.use_amp = (
            use_amp and self.device.type == "cuda" and torch.cuda.is_available()
        )
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event

        self.model = self.model.to(self.device)

        self.optimizer = self._create_optimizer()
        self.lr_scheduler = self._create_lr_scheduler()
        self.criterion = self._create_criterion()

        self.scaler = torch.cuda.amp.GradScaler() if self.use_amp else None

        self.current_epoch = 0
        self.best_val_loss = float("inf")
        self.patience_counter = 0
        self.training_history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "train_accuracy": [],
            "val_accuracy": [],
            "learning_rate": [],
        }

        self.best_model_state: Optional[Dict[str, Any]] = None

        self._log_device_info()

    def _log_device_info(self) -> None:
        """记录训练设备信息到日志"""
        if self.device.type == "cuda":
            gpu_index = self.device.index if self.device.index is not None else 0
            props = torch.cuda.get_device_properties(gpu_index)
            vram_mb = props.total_memory / (1024**2)
            logger.info(
                f"Training on GPU: {props.name} "
                f"(VRAM: {vram_mb:.0f}MB, CUDA: {torch.version.cuda}, "
                f"Compute: {props.major}.{props.minor})"
            )
            if self.use_amp:
                logger.info("Mixed precision training (AMP) enabled")
        else:
            logger.info("Training on CPU")

    def _create_optimizer(self) -> torch.optim.Optimizer:
        """创建优化器"""
        if self.optimizer_type == "adam":
            return torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)
        elif self.optimizer_type == "adamw":
            return torch.optim.AdamW(self.model.parameters(), lr=self.learning_rate)
        elif self.optimizer_type == "sgd":
            return torch.optim.SGD(
                self.model.parameters(), lr=self.learning_rate, momentum=0.9
            )
        elif self.optimizer_type == "rmsprop":
            return torch.optim.RMSprop(self.model.parameters(), lr=self.learning_rate)
        else:
            return torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def _create_lr_scheduler(self) -> Optional[torch.optim.lr_scheduler._LRScheduler]:
        """创建学习率调度器"""
        if self.lr_scheduler_type == "step":
            step_size = self.lr_scheduler_params.get("step_size", 30)
            gamma = self.lr_scheduler_params.get("gamma", 0.1)
            return torch.optim.lr_scheduler.StepLR(
                self.optimizer, step_size=step_size, gamma=gamma
            )
        elif self.lr_scheduler_type == "cosine":
            T_max = self.lr_scheduler_params.get("T_max", self.epochs)
            eta_min = self.lr_scheduler_params.get("eta_min", 0)
            return torch.optim.lr_scheduler.CosineAnnealingLR(
                self.optimizer, T_max=T_max, eta_min=eta_min
            )
        elif self.lr_scheduler_type == "reduce_on_plateau":
            mode = self.lr_scheduler_params.get("mode", "min")
            factor = self.lr_scheduler_params.get("factor", 0.1)
            patience = self.lr_scheduler_params.get("patience", 10)
            return torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer, mode=mode, factor=factor, patience=patience
            )
        elif self.lr_scheduler_type == "exponential":
            gamma = self.lr_scheduler_params.get("gamma", 0.95)
            return torch.optim.lr_scheduler.ExponentialLR(self.optimizer, gamma=gamma)
        else:
            return None

    def _create_criterion(self) -> nn.Module:
        """创建损失函数"""
        if self.loss_type == "cross_entropy":
            return nn.CrossEntropyLoss()
        elif self.loss_type == "mse":
            return nn.MSELoss()
        elif self.loss_type == "mae":
            return nn.L1Loss()
        elif self.loss_type == "bce":
            return nn.BCELoss()
        elif self.loss_type == "bce_with_logits":
            return nn.BCEWithLogitsLoss()
        else:
            return nn.CrossEntropyLoss()

    def train_epoch(self, dataloader: DataLoader) -> Tuple[float, float]:
        """
        实现单个epoch的训练逻辑，支持混合精度训练

        Args:
            dataloader: 训练数据加载器

        Returns:
            (训练损失, 训练准确率)
        """
        self.model.train()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        for batch_X, batch_y in dataloader:
            batch_X = batch_X.to(self.device)
            batch_y = batch_y.to(self.device)

            self.optimizer.zero_grad()

            if self.use_amp and self.scaler is not None:
                with torch.cuda.amp.autocast():
                    outputs = self.model(batch_X)
                    if isinstance(outputs, tuple):
                        outputs = outputs[0]
                        if (
                            hasattr(self.model, "hidden_state")
                            and self.model.hidden_state is not None
                        ):
                            self.model.hidden_state = self.model.hidden_state.detach()

                    loss = self.criterion(outputs, batch_y)

                self.scaler.scale(loss).backward()

                if self.gradient_clip_value is not None:
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(), self.gradient_clip_value
                    )

                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                outputs = self.model(batch_X)
                if isinstance(outputs, tuple):
                    outputs = outputs[0]
                    if (
                        hasattr(self.model, "hidden_state")
                        and self.model.hidden_state is not None
                    ):
                        self.model.hidden_state = self.model.hidden_state.detach()

                loss = self.criterion(outputs, batch_y)

                loss.backward()

                if self.gradient_clip_value is not None:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(), self.gradient_clip_value
                    )

                self.optimizer.step()

            total_loss += loss.item() * batch_X.size(0)
            if self.loss_type in ["cross_entropy", "bce_with_logits"]:
                preds = torch.argmax(outputs, dim=1)
                true_labels = (
                    torch.argmax(batch_y, dim=1) if batch_y.ndim > 1 else batch_y
                )
            elif self.loss_type == "bce":
                preds = (outputs > 0.5).float()
                true_labels = batch_y
            else:
                preds = outputs
                true_labels = batch_y

            total_correct += (preds == true_labels).sum().item()
            total_samples += batch_X.size(0)

        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples

        return avg_loss, accuracy

    def validate(self, dataloader: DataLoader) -> Tuple[float, float]:
        """
        实现模型验证逻辑

        Args:
            dataloader: 验证数据加载器

        Returns:
            (验证损失, 验证准确率)
        """
        self.model.eval()
        total_loss = 0.0
        total_correct = 0
        total_samples = 0

        with torch.no_grad():
            for batch_X, batch_y in dataloader:
                batch_X = batch_X.to(self.device)
                batch_y = batch_y.to(self.device)

                if self.use_amp:
                    with torch.cuda.amp.autocast():
                        outputs = self.model(batch_X)
                        if isinstance(outputs, tuple):
                            outputs = outputs[0]
                            if (
                                hasattr(self.model, "hidden_state")
                                and self.model.hidden_state is not None
                            ):
                                self.model.hidden_state = (
                                    self.model.hidden_state.detach()
                                )
                        loss = self.criterion(outputs, batch_y)
                else:
                    outputs = self.model(batch_X)
                    if isinstance(outputs, tuple):
                        outputs = outputs[0]
                        if (
                            hasattr(self.model, "hidden_state")
                            and self.model.hidden_state is not None
                        ):
                            self.model.hidden_state = self.model.hidden_state.detach()
                    loss = self.criterion(outputs, batch_y)

                total_loss += loss.item() * batch_X.size(0)

                if self.loss_type in ["cross_entropy", "bce_with_logits"]:
                    preds = torch.argmax(outputs, dim=1)
                    true_labels = (
                        torch.argmax(batch_y, dim=1) if batch_y.ndim > 1 else batch_y
                    )
                elif self.loss_type == "bce":
                    preds = (outputs > 0.5).float()
                    true_labels = batch_y
                else:
                    preds = outputs
                    true_labels = batch_y

                total_correct += (preds == true_labels).sum().item()
                total_samples += batch_X.size(0)

        avg_loss = total_loss / total_samples
        accuracy = total_correct / total_samples

        return avg_loss, accuracy

    def fit(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        epochs: Optional[int] = None,
    ) -> Dict[str, List[float]]:
        """
        实现完整训练流程

        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            epochs: 训练轮数 (如果为None则使用初始化时的设置)

        Returns:
            训练历史
        """
        epochs = epochs or self.epochs

        device_info = self.device.type.upper()
        if self.device.type == "cuda":
            gpu_index = self.device.index if self.device.index is not None else 0
            device_info = (
                f"CUDA:{gpu_index} ({torch.cuda.get_device_properties(gpu_index).name})"
            )

        logger.info("Starting training for %s epochs...", epochs)
        logger.info(
            "Optimizer: %s, LR: %s, Loss: %s",
            self.optimizer_type,
            self.learning_rate,
            self.loss_type,
        )
        logger.info(
            "Device: %s | AMP: %s",
            device_info,
            "enabled" if self.use_amp else "disabled",
        )

        training_start = time.perf_counter()

        for epoch in range(epochs):
            self.current_epoch = epoch + 1

            if self.cancel_event and self.cancel_event.is_set():
                logger.info("Training cancelled at epoch %s", epoch + 1)
                raise asyncio.CancelledError("Training cancelled by user")

            epoch_start = time.perf_counter()
            train_loss, train_acc = self.train_epoch(train_loader)
            epoch_time = time.perf_counter() - epoch_start

            val_loss, val_acc = self.validate(val_loader)

            self.training_history["train_loss"].append(train_loss)
            self.training_history["train_accuracy"].append(train_acc)
            self.training_history["val_loss"].append(val_loss)
            self.training_history["val_accuracy"].append(val_acc)
            self.training_history["learning_rate"].append(
                self.optimizer.param_groups[0]["lr"]
            )

            if self.progress_callback:
                try:
                    metrics = {
                        "train_accuracy": round(train_acc, 4),
                        "val_accuracy": round(val_acc, 4),
                        "train_loss": round(train_loss, 4),
                        "val_loss": round(val_loss, 4),
                    }
                    self.progress_callback(
                        epoch=self.current_epoch,
                        loss=val_loss,
                        metrics=metrics,
                    )
                except Exception as cb_err:
                    logger.warning(f"Progress callback failed: {cb_err}")

            device_display = device_info
            if self.device.type == "cuda" and epoch % 10 == 0:
                gpu_index = self.device.index if self.device.index is not None else 0
                mem_used_mb = torch.cuda.memory_allocated(gpu_index) / (1024**2)
                mem_reserved_mb = torch.cuda.memory_reserved(gpu_index) / (1024**2)
                device_display = f"{device_info} | GPU Mem: {mem_used_mb:.0f}/{mem_reserved_mb:.0f}MB"

            log_msg = (
                f"Epoch {epoch + 1}/{epochs} | "
                f"Device: {device_display} | "
                f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f} | "
                f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f} | "
                f"Time: {epoch_time:.2f}s"
            )
            logger.info(log_msg)

            self._step_lr_scheduler(val_loss)

            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                self.best_model_state = self._save_model_state()
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.early_stopping_patience:
                    logger.info("Early stopping at epoch %s", epoch + 1)
                    break

            if self.device.type == "cuda" and not check_gpu_memory_safe(
                threshold_percent=95.0
            ):
                logger.warning("GPU memory usage high, clearing cache")
                clear_gpu_memory(self.device)

        if self.best_model_state is not None:
            self._restore_model_state(self.best_model_state)
            logger.info("Restored best model with val_loss: %.4f", self.best_val_loss)

        total_training_time = time.perf_counter() - training_start
        logger.info(
            "Training completed in %.2fs (%.2fs/epoch)",
            total_training_time,
            total_training_time / epochs,
        )

        self.model.is_trained = True
        return self.training_history

    def _step_lr_scheduler(self, val_loss: Optional[float] = None):
        """执行学习率调度"""
        if self.lr_scheduler is None:
            return

        if isinstance(self.lr_scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
            self.lr_scheduler.step(val_loss)
        else:
            self.lr_scheduler.step()

    def _save_model_state(self) -> Dict[str, Any]:
        return {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }

    def _restore_model_state(self, state: Dict[str, Any]) -> None:
        """恢复模型状态"""
        self.model.load_state_dict(state["model_state_dict"])
        self.optimizer.load_state_dict(state["optimizer_state_dict"])

    def save_checkpoint(
        self,
        path: str,
        epoch: Optional[int] = None,
        metrics: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        实现检查点保存功能

        Args:
            path: 保存路径
            epoch: 当前epoch (如果为None则使用self.current_epoch)
            metrics: 性能指标
        """
        checkpoint = {
            "epoch": epoch if epoch is not None else self.current_epoch,
            "best_val_loss": self.best_val_loss,
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "training_history": self.training_history,
            "model_config": {
                "optimizer_type": self.optimizer_type,
                "loss_type": self.loss_type,
                "learning_rate": self.learning_rate,
                "gradient_clip_value": self.gradient_clip_value,
                "lr_scheduler_type": self.lr_scheduler_type,
            },
            "metrics": metrics or {},
            "timestamp": datetime.now().isoformat(),
            "device": str(self.device),
            "use_amp": self.use_amp,
            "scaler_state_dict": self.scaler.state_dict()
            if self.scaler is not None
            else None,
        }

        os.makedirs(
            os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True
        )
        torch.save(checkpoint, path)
        logger.info("Checkpoint saved to %s", path)

    def load_checkpoint(self, path: str) -> Dict[str, Any]:
        """
        实现检查点加载功能

        Args:
            path: 检查点路径

        Returns:
            检查点信息
        """
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"训练检查点加载失败：找不到检查点文件 '{path}'。可能原因：文件路径错误或检查点已被删除/移动。请确认：1) 路径 '{path}' 是否正确；2) 文件是否存在于预期位置；3) 如需重新训练，请调用 POST /api/v1/lnn/models/train 启动新训练任务。"
            )

        checkpoint = torch.load(path, map_location=self.device)

        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.current_epoch = checkpoint.get("epoch", 0)
        self.best_val_loss = checkpoint.get("best_val_loss", float("inf"))
        self.training_history = checkpoint.get(
            "training_history", self.training_history
        )

        if self.scaler is not None and checkpoint.get("scaler_state_dict") is not None:
            self.scaler.load_state_dict(checkpoint["scaler_state_dict"])

        logger.info("Checkpoint loaded from %s", path)
        return checkpoint

    def export_torchscript(
        self, save_path: str, example_input: Optional[torch.Tensor] = None
    ) -> str:
        """
        导出模型为TorchScript格式

        Args:
            save_path: 保存路径（.pt或.torchscript）
            example_input: 示例输入张量用于trace

        Returns:
            保存的文件路径
        """
        self.model.eval()

        if example_input is None:
            example_input = torch.randn(1, self.model.input_dim, device=self.device)

        if hasattr(self.model, "reset"):
            self.model.reset()

        with torch.no_grad():
            scripted = torch.jit.trace(self.model, example_input, check_trace=False)

        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)

        scripted.save(save_path)
        logger.info("TorchScript model exported to %s", save_path)

        return save_path

    def get_training_summary(self) -> Dict[str, Any]:
        """获取训练摘要"""
        summary = {
            "total_epochs": self.current_epoch,
            "best_val_loss": self.best_val_loss,
            "final_train_loss": self.training_history["train_loss"][-1]
            if self.training_history["train_loss"]
            else None,
            "final_val_loss": self.training_history["val_loss"][-1]
            if self.training_history["val_loss"]
            else None,
            "final_train_accuracy": self.training_history["train_accuracy"][-1]
            if self.training_history["train_accuracy"]
            else None,
            "final_val_accuracy": self.training_history["val_accuracy"][-1]
            if self.training_history["val_accuracy"]
            else None,
            "optimizer": self.optimizer_type,
            "loss_function": self.loss_type,
            "device": str(self.device),
            "use_amp": self.use_amp,
        }

        if self.device.type == "cuda":
            gpu_index = self.device.index if self.device.index is not None else 0
            summary["gpu_name"] = torch.cuda.get_device_properties(gpu_index).name
            summary["gpu_max_memory_mb"] = round(
                torch.cuda.max_memory_allocated(gpu_index) / (1024**2), 2
            )

        return summary
