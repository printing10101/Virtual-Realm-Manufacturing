"""
实验10: 消融实验

验证CT-LTC各核心组件的贡献:
- PCC Loss (物理一致性损失)
- 解析预训练 (两阶段训练策略)
- LTC vs LSTM (连续时间 vs 离散时间)
- 门控融合机制

实验目标:
- 量化每个组件对最终性能的贡献
- 验证论文核心创新点的有效性
- 为论文消融实验章节提供数据支撑
"""

import os
import sys
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import DataLoader
from typing import Dict, List
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from config import ExperimentConfig
from data_generator import SyntheticChatterDataset, IndustrialChatterDataset
from models import CTCTCWithPhysics, CTLTCModel, BaselineLSTM, BaselineBPNN, create_model
from losses import PCC_Loss
from metrics import ChatterMetrics as Metrics
from trainer import CTCTCTrainer, BaselineTrainer


class AblationExperiment:
    """消融实验"""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.device = torch.device(config.model.device if torch.cuda.is_available() else "cpu")
        self.results = {}
    
    def run_ablation_study(
        self,
        dataset_class,
        dataset_params: Dict
    ) -> Dict[str, Dict[str, float]]:
        """
        运行消融实验
        
        实验变体:
        1. Full Model (完整CT-LTC)
        2. w/o PCC Loss (移除物理一致性损失)
        3. w/o Pre-train (移除解析预训练)
        4. LTC → LSTM (替换为离散时间网络)
        5. w/o Gate (移除门控融合)
        
        Args:
            dataset_class: 数据集类
            dataset_params: 数据集参数
        
        Returns:
            结果字典 {variant_name: {metric: value}}
        """
        print("\n" + "=" * 60)
        print("消融实验: 核心组件贡献分析")
        print("=" * 60)
        
        # 准备数据
        train_dataset = dataset_class(**dataset_params)
        test_dataset = dataset_class(**{**dataset_params, 'seed': 123})
        
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.model.batch_size,
            shuffle=True
        )
        test_loader = DataLoader(
            test_dataset,
            batch_size=self.config.model.batch_size,
            shuffle=False
        )
        
        ablation_results = {}
        
        # 1. Full Model (完整CT-LTC)
        print("\n[1/5] Full Model (CT-LTC + PCC Loss + Pre-train + Gate)")
        print("-" * 60)
        # 移除手动模型创建，使用trainer内部模型创建
        trainer = CTCTCTrainer(self.config, self.device)
        trainer.train(train_loader, test_loader)
        full_metrics = trainer.evaluate(test_loader)
        ablation_results['Full Model'] = full_metrics
        
        print(f"  MAE: {full_metrics['MAE']:.3f}, "
              f"PCC: {full_metrics['PCC']:.3f}, "
              f"R²: {full_metrics['R²']:.3f}")
        
        # 2. w/o PCC Loss (移除物理一致性损失)
        print("\n[2/5] w/o PCC Loss (仅使用数据损失)")
        print("-" * 60)
        # 修改配置,禁用PCC Loss
        config_no_pcc = ExperimentConfig()
        config_no_pcc.model.lambda_pcc = 0.0
        config_no_pcc.model.lambda_phys = 0.0
        
        trainer_no_pcc = CTCTCTrainer(config_no_pcc, self.device)
        trainer_no_pcc.train(train_loader, test_loader)
        no_pcc_metrics = trainer_no_pcc.evaluate(test_loader)
        ablation_results['w/o PCC Loss'] = no_pcc_metrics
        
        print(f"  MAE: {no_pcc_metrics['MAE']:.3f}, "
              f"PCC: {no_pcc_metrics['PCC']:.3f}, "
              f"R²: {no_pcc_metrics['R²']:.3f}")
        
        # 3. w/o Pre-train (移除解析预训练)
        print("\n[3/5] w/o Pre-train (直接从零训练)")
        print("-" * 60)
        model_no_pretrain = CTCTCWithPhysics(
            input_dim=self.config.model.input_dim,
            hidden_dim=self.config.model.hidden_dim,
            num_layers=self.config.model.num_layers,
            dropout=self.config.model.dropout
        ).to(self.device)
        
        config_no_pretrain = ExperimentConfig()
        config_no_pretrain.model.num_epochs_stage1 = 0  # 跳过预训练
        
        trainer_no_pretrain = CTCTCTrainer(config_no_pretrain, self.device)
        trainer_no_pretrain.train(train_loader, test_loader)
        no_pretrain_metrics = trainer_no_pretrain.evaluate(test_loader)
        ablation_results['w/o Pre-train'] = no_pretrain_metrics
        
        print(f"  MAE: {no_pretrain_metrics['MAE']:.3f}, "
              f"PCC: {no_pretrain_metrics['PCC']:.3f}, "
              f"R²: {no_pretrain_metrics['R²']:.3f}")
        
        # 4. LTC → LSTM (替换为离散时间网络)
        print("\n[4/5] LTC → LSTM (离散时间网络)")
        print("-" * 60)
        lstm_model = BaselineLSTM(
            input_dim=self.config.model.input_dim,
            hidden_dim=self.config.model.hidden_dim,
            num_layers=self.config.model.num_layers,
            output_dim=1
        ).to(self.device)
        
        lstm_metrics = self._train_baseline(lstm_model, train_loader, test_loader)
        ablation_results['LTC → LSTM'] = lstm_metrics
        
        print(f"  MAE: {lstm_metrics['MAE']:.3f}, "
              f"PCC: {lstm_metrics['PCC']:.3f}, "
              f"R²: {lstm_metrics['R²']:.3f}")
        
        # 5. w/o Gate (移除门控融合,直接相加)
        print("\n[5/5] w/o Gate (移除门控融合机制)")
        print("-" * 60)
        # 简化处理：使用标准LTC模型代替（无门控融合）
        model_no_gate = CTLTCModel(
            input_dim=self.config.model.input_dim,
            hidden_dim=self.config.model.hidden_dim,
            num_layers=self.config.model.num_layers,
            output_dim=1,
            dropout=self.config.model.dropout
        ).to(self.device)
        
        no_gate_metrics = self._train_baseline(model_no_gate, train_loader, test_loader)
        ablation_results['w/o Gate'] = no_gate_metrics
        
        print(f"  MAE: {no_gate_metrics['MAE']:.3f}, "
              f"PCC: {no_gate_metrics['PCC']:.3f}, "
              f"R²: {no_gate_metrics['R²']:.3f}")
        
        # 计算相对改进
        print("\n" + "=" * 60)
        print("消融实验结果汇总")
        print("=" * 60)
        
        baseline_mae = ablation_results['Full Model']['MAE']
        
        for variant, metrics in ablation_results.items():
            if variant != 'Full Model':
                degradation = (metrics['MAE'] - baseline_mae) / baseline_mae * 100
                print(f"{variant:20s}: MAE={metrics['MAE']:.3f} "
                      f"(+{degradation:.1f}% vs Full)")
        
        self.results['ablation'] = ablation_results
        return ablation_results
    
    def _train_baseline(
        self,
        model: torch.nn.Module,
        train_loader: DataLoader,
        test_loader: DataLoader,
        num_epochs: int = 200
    ) -> Dict[str, float]:
        """训练基线模型"""
        optimizer = torch.optim.Adam(
            model.parameters(),
            lr=self.config.model.learning_rate,
            weight_decay=self.config.model.weight_decay
        )
        criterion = torch.nn.L1Loss()
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=num_epochs
        )
        
        # 训练
        model.train()
        for epoch in range(num_epochs):
            train_loss = 0.0
            for batch_x, batch_y, batch_y_phys in train_loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                optimizer.zero_grad()
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
            
            scheduler.step()
        
        # 评估
        model.eval()
        all_preds = []
        all_targets = []
        all_phys = []
        
        with torch.no_grad():
            for batch_x, batch_y, batch_y_phys in test_loader:
                batch_x = batch_x.to(self.device)
                outputs = model(batch_x)
                
                all_preds.extend(outputs.cpu().numpy())
                all_targets.extend(batch_y.numpy())
                all_phys.extend(batch_y_phys.numpy())
        
        all_preds = np.array(all_preds)
        all_targets = np.array(all_targets)
        all_phys = np.array(all_phys)
        
        # 计算指标
        metrics = {
            'MAE': Metrics.mae(all_preds, all_targets),
            'RMSE': Metrics.rmse(all_preds, all_targets),
            'R²': Metrics.r2_score(all_preds, all_targets),
            'PCC': Metrics.physics_consistency_coefficient(all_preds, all_phys)
        }
        
        return metrics
    
    def save_results(self, save_path: str = "results/ablation_results.json"):
        """保存实验结果"""
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 消融实验结果已保存: {save_path}")


def main():
    """主函数"""
    print("=" * 60)
    print("实验10: 消融实验")
    print("=" * 60)
    
    # 加载配置
    config = ExperimentConfig()
    
    # 创建实验器
    experiment = AblationExperiment(config)
    
    # 在工业数据集上运行消融实验
    dataset_params = {
        'num_samples': 500,
        'num_conditions': 30,
        'material': '6061-T6'
    }
    
    ablation_results = experiment.run_ablation_study(
        IndustrialChatterDataset,
        dataset_params
    )
    
    # 保存结果
    experiment.save_results()
    
    print("\n" + "=" * 60)
    print("✓ 消融实验完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
