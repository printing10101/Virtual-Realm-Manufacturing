"""
训练器模块
实现两阶段训练策略
"""

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from typing import Dict, List, Tuple
import os
from datetime import datetime
import json

from models import create_model
from losses import PCC_Loss
from metrics import MetricsTracker, ChatterMetrics
from config import ExperimentConfig


class CTCTCTrainer:
    """
    CT-LTC 训练器
    实现两阶段训练策略
    """
    
    def __init__(
        self,
        config: ExperimentConfig,
        device: str = "cuda"
    ):
        self.config = config
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        
        # 创建模型
        self.model = create_model("CT-LTC", config).to(self.device)
        
        # 损失函数
        self.criterion = PCC_Loss(
            epsilon_phys=config.model.epsilon_phys,
            lambda_phys=config.model.lambda_phys,
            lambda_pcc=config.model.lambda_pcc
        )
        
        # 优化器
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=config.model.learning_rate,
            weight_decay=config.model.weight_decay
        )
        
        # 学习率调度器
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer,
            T_max=config.model.num_epochs_stage2,
            eta_min=1e-5
        )
        
        # 训练历史
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_metrics': [],
            'val_metrics': []
        }
        
        # 最佳模型
        self.best_val_loss = float('inf')
        self.best_model_state = None
    
    def train_stage1(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        num_epochs: int = None
    ) -> Dict:
        """
        阶段一：解析预训练
        使用合成数据训练，仅用数据损失
        
        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            num_epochs: 训练轮数
        
        Returns:
            训练历史
        """
        if num_epochs is None:
            num_epochs = self.config.model.num_epochs_stage1
        
        print(f"\n{'='*60}")
        print(f"阶段一：解析预训练 ({num_epochs} epochs)")
        print(f"{'='*60}")
        
        for epoch in range(num_epochs):
            # 训练
            train_loss, train_metrics = self._train_epoch(
                train_loader, stage=1
            )
            
            # 验证
            val_loss, val_metrics = self._validate(val_loader, stage=1)
            
            # 记录历史
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['train_metrics'].append(train_metrics)
            self.history['val_metrics'].append(val_metrics)
            
            # 打印进度
            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"Epoch [{epoch+1}/{num_epochs}]")
                print(f"  Train Loss: {train_loss:.4f} | MAE: {train_metrics['mae']:.4f}")
                print(f"  Val Loss: {val_loss:.4f} | MAE: {val_metrics['mae']:.4f}")
        
        return self.history
    
    def train_stage2(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        num_epochs: int = None
    ) -> Dict:
        """
        阶段二：物理残差微调
        使用真实数据训练，使用完整损失（数据+物理+梯度）
        
        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            num_epochs: 训练轮数
        
        Returns:
            训练历史
        """
        if num_epochs is None:
            num_epochs = self.config.model.num_epochs_stage2
        
        print(f"\n{'='*60}")
        print(f"阶段二：物理残差微调 ({num_epochs} epochs)")
        print(f"{'='*60}")
        
        for epoch in range(num_epochs):
            # 训练
            train_loss, train_metrics = self._train_epoch(
                train_loader, stage=2
            )
            
            # 验证
            val_loss, val_metrics = self._validate(val_loader, stage=2)
            
            # 记录历史
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['train_metrics'].append(train_metrics)
            self.history['val_metrics'].append(val_metrics)
            
            # 保存最佳模型
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.best_model_state = self.model.state_dict().copy()
                print(f"  ✓ 保存最佳模型 (Val Loss: {val_loss:.4f})")
            
            # 打印进度
            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"Epoch [{epoch+1}/{num_epochs}]")
                print(f"  Train Loss: {train_loss:.4f} | MAE: {train_metrics['mae']:.4f} | PCC: {train_metrics.get('pcc', 0):.4f}")
                print(f"  Val Loss: {val_loss:.4f} | MAE: {val_metrics['mae']:.4f} | PCC: {val_metrics.get('pcc', 0):.4f}")
            
            # 更新学习率
            self.scheduler.step()
        
        # 加载最佳模型
        if self.best_model_state is not None:
            self.model.load_state_dict(self.best_model_state)
        
        return self.history
    
    def _train_epoch(
        self,
        train_loader: DataLoader,
        stage: int = 1
    ) -> Tuple[float, Dict]:
        """
        训练一个epoch
        
        Args:
            train_loader: 训练数据加载器
            stage: 训练阶段 (1或2)
        
        Returns:
            平均损失和指标字典
        """
        self.model.train()
        metrics_tracker = MetricsTracker()
        total_loss = 0.0
        num_batches = 0
        
        for batch in train_loader:
            # 解包数据
            x, y_true, y_physics = self._unpack_batch(batch)
            
            # 阶段二需要计算梯度，为输入启用梯度
            if stage == 2:
                x.requires_grad_(True)
            
            # 前向传播
            self.optimizer.zero_grad()
            
            if stage == 1:
                # 阶段一：仅使用数据损失
                y_pred, _ = self.model(x)
                loss = torch.mean(torch.abs(y_pred - y_true))
            else:
                # 阶段二：使用完整损失（数据+物理+梯度）
                y_pred, _ = self.model(x)
                loss, _ = self.criterion(y_pred, y_true, y_physics, x, self.model)
            
            # 反向传播
            loss.backward()
            self.optimizer.step()
            
            # 记录指标
            total_loss += loss.item()
            metrics_tracker.update(y_pred, y_true, y_physics)
            num_batches += 1
        
        # 计算平均指标
        avg_loss = total_loss / num_batches
        metrics = metrics_tracker.compute()
        
        return avg_loss, metrics
    
    def _validate(
        self,
        val_loader: DataLoader,
        stage: int = 1
    ) -> Tuple[float, Dict]:
        """
        验证
        
        Args:
            val_loader: 验证数据加载器
            stage: 训练阶段
        
        Returns:
            平均损失和指标字典
        """
        self.model.eval()
        metrics_tracker = MetricsTracker()
        total_loss = 0.0
        num_batches = 0
        
        if stage == 1:
            # 阶段一：仅使用数据损失，可以完全在 no_grad 下进行
            with torch.no_grad():
                for batch in val_loader:
                    x, y_true, y_physics = self._unpack_batch(batch)
                    y_pred, _ = self.model(x)
                    loss = torch.mean(torch.abs(y_pred - y_true))
                    
                    total_loss += loss.item()
                    metrics_tracker.update(y_pred, y_true, y_physics)
                    num_batches += 1
        else:
            # 阶段二：需要计算梯度，不能完全在 no_grad 下进行
            for batch in val_loader:
                x, y_true, y_physics = self._unpack_batch(batch)
                x.requires_grad_(True)  # 需要梯度
                
                y_pred, _ = self.model(x)
                loss, _ = self.criterion(y_pred, y_true, y_physics, x, self.model)
                
                total_loss += loss.item()
                metrics_tracker.update(y_pred, y_true, y_physics)
                num_batches += 1
        
        # 计算平均指标
        avg_loss = total_loss / num_batches
        metrics = metrics_tracker.compute()
        
        return avg_loss, metrics
    
    def _unpack_batch(self, batch):
        """
        解包批次数据
        
        Args:
            batch: 批次数据
        
        Returns:
            x, y_true, y_physics
        """
        if len(batch) == 3:
            x, y_true, y_physics = batch
            x = x.to(self.device)
            y_true = y_true.to(self.device)
            y_physics = y_physics.to(self.device)
        else:
            x, y_true = batch
            x = x.to(self.device)
            y_true = y_true.to(self.device)
            y_physics = None
        
        return x, y_true, y_physics
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader
    ) -> Dict:
        """
        完整训练流程（两阶段）
        
        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
        
        Returns:
            训练历史
        """
        # 阶段一：解析预训练
        self.train_stage1(train_loader, val_loader)
        
        # 阶段二：物理残差微调
        self.train_stage2(train_loader, val_loader)
        
        return self.history
    
    def evaluate(
        self,
        test_loader: DataLoader
    ) -> Dict[str, float]:
        """
        评估模型
        
        Args:
            test_loader: 测试数据加载器
        
        Returns:
            评估指标字典
        """
        self.model.eval()
        all_preds = []
        all_targets = []
        all_phys = []
        
        with torch.no_grad():
            for batch in test_loader:
                x, y_true, y_physics = self._unpack_batch(batch)
                y_pred, _ = self.model(x)
                
                all_preds.extend(y_pred.cpu().detach().numpy())
                all_targets.extend(y_true.cpu().numpy())
                if y_physics is not None:
                    all_phys.extend(y_physics.cpu().numpy())
        
        import numpy as np
        all_preds = np.array(all_preds)
        all_targets = np.array(all_targets)
        all_phys = np.array(all_phys) if all_phys else all_targets
        
        # 计算指标
        from metrics import ChatterMetrics
        metrics = {
            'MAE': ChatterMetrics.mae(all_preds, all_targets),
            'RMSE': ChatterMetrics.rmse(all_preds, all_targets),
            'R²': ChatterMetrics.r2_score(all_preds, all_targets),
            'PCC': ChatterMetrics.physics_consistency_coefficient(all_preds, all_phys)
        }
        
        return metrics
    
    def save_checkpoint(self, path: str):
        """
        保存检查点
        
        Args:
            path: 保存路径
        """
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'scheduler_state_dict': self.scheduler.state_dict(),
            'history': self.history,
            'best_val_loss': self.best_val_loss,
            'config': self.config.__dict__
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(checkpoint, path)
        print(f"检查点已保存: {path}")
    
    def load_checkpoint(self, path: str):
        """
        加载检查点
        
        Args:
            path: 检查点路径
        """
        checkpoint = torch.load(path, map_location=self.device)
        
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
        self.scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
        self.history = checkpoint['history']
        self.best_val_loss = checkpoint['best_val_loss']
        
        print(f"检查点已加载: {path}")
    
    def save_history(self, path: str):
        """
        保存训练历史
        
        Args:
            path: 保存路径
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
        print(f"训练历史已保存: {path}")


class BaselineTrainer:
    """
    基线模型训练器
    用于训练LSTM、Transformer、PINN等基线模型
    """
    
    def __init__(
        self,
        model_name: str,
        config: ExperimentConfig,
        device: str = "cuda"
    ):
        self.model_name = model_name
        self.config = config
        self.device = torch.device(device if torch.cuda.is_available() else "cpu")
        
        # 创建模型
        self.model = create_model(model_name, config).to(self.device)
        
        # 损失函数（仅使用MSE）
        self.criterion = nn.MSELoss()
        
        # 优化器
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=config.model.learning_rate
        )
        
        # 训练历史
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_metrics': [],
            'val_metrics': []
        }
    
    def train(
        self,
        train_loader: DataLoader,
        val_loader: DataLoader,
        num_epochs: int = 100
    ) -> Dict:
        """
        训练基线模型
        
        Args:
            train_loader: 训练数据加载器
            val_loader: 验证数据加载器
            num_epochs: 训练轮数
        
        Returns:
            训练历史
        """
        print(f"\n{'='*60}")
        print(f"训练 {self.model_name} ({num_epochs} epochs)")
        print(f"{'='*60}")
        
        best_val_loss = float('inf')
        
        for epoch in range(num_epochs):
            # 训练
            self.model.train()
            train_loss = 0.0
            metrics_tracker = MetricsTracker()
            
            for batch in train_loader:
                x, y_true, _ = batch
                x = x.to(self.device)
                y_true = y_true.to(self.device)
                
                self.optimizer.zero_grad()
                y_pred = self.model(x)
                loss = self.criterion(y_pred, y_true)
                loss.backward()
                self.optimizer.step()
                
                train_loss += loss.item()
                metrics_tracker.update(y_pred, y_true)
            
            train_loss /= len(train_loader)
            train_metrics = metrics_tracker.compute()
            
            # 验证
            self.model.eval()
            val_loss = 0.0
            metrics_tracker.reset()
            
            with torch.no_grad():
                for batch in val_loader:
                    x, y_true, _ = batch
                    x = x.to(self.device)
                    y_true = y_true.to(self.device)
                    
                    y_pred = self.model(x)
                    loss = self.criterion(y_pred, y_true)
                    
                    val_loss += loss.item()
                    metrics_tracker.update(y_pred, y_true)
            
            val_loss /= len(val_loader)
            val_metrics = metrics_tracker.compute()
            
            # 记录历史
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['train_metrics'].append(train_metrics)
            self.history['val_metrics'].append(val_metrics)
            
            # 打印进度
            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"Epoch [{epoch+1}/{num_epochs}]")
                print(f"  Train Loss: {train_loss:.4f} | MAE: {train_metrics['mae']:.4f}")
                print(f"  Val Loss: {val_loss:.4f} | MAE: {val_metrics['mae']:.4f}")
        
        return self.history


if __name__ == "__main__":
    # 测试训练器
    print("测试训练器...")
    
    config = ExperimentConfig()
    trainer = CTCTCTrainer(config, device="cpu")
    
    print(f"模型参数量: {sum(p.numel() for p in trainer.model.parameters()):,}")
    print(f"设备: {trainer.device}")
    
    print("\n训练器测试通过！")
