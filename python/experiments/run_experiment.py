"""
主实验脚本
运行所有数据集上的所有模型对比实验
"""

import sys
import os
import json
import numpy as np
import torch
from torch.utils.data import DataLoader
from typing import Dict, List
import time

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from experiments.config import get_config
from experiments.data_generator import SyntheticChatterDataset, IndustrialChatterDataset
from experiments.models import create_model
from experiments.trainer import CTCTCTrainer, BaselineTrainer
from experiments.metrics import ChatterMetrics
from experiments.losses import PCC_Loss


def run_single_dataset_experiment(
    config,
    dataset_name: str,
    dataset_class,
    dataset_kwargs: dict
) -> Dict[str, Dict[str, float]]:
    """
    在单个数据集上运行所有模型实验
    
    Args:
        config: 实验配置
        dataset_name: 数据集名称
        dataset_class: 数据集类
        dataset_kwargs: 数据集参数
    
    Returns:
        实验结果字典
    """
    print(f"\n{'='*80}")
    print(f"数据集: {dataset_name}")
    print(f"{'='*80}\n")
    
    # 创建数据集
    full_dataset = dataset_class(**dataset_kwargs)
    
    # 划分训练集、验证集、测试集
    train_size = int(0.7 * len(full_dataset))
    val_size = int(0.15 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size, test_size]
    )
    
    # 创建数据加载器
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)
    
    # 定义所有模型
    model_names = [
        "CT-LTC",  # 本文方法
        "LSTM",
        "Transformer",
        "PINN",
        "BPNN"
    ]
    
    results = {}
    
    # 训练和评估每个模型
    for model_name in model_names:
        print(f"\n训练模型: {model_name}")
        print("-" * 60)
        
        # 选择训练器
        if model_name == "CT-LTC":
            trainer = CTCTCTrainer(config, device=config.model.device)
            # 阶段一：预训练
            trainer.train_stage1(train_loader, val_loader, num_epochs=20)
            # 阶段二：微调
            trainer.train_stage2(train_loader, val_loader, num_epochs=30)
            model = trainer.model
        else:
            trainer = BaselineTrainer(model_name, config, device=config.model.device)
            trainer.train(train_loader, val_loader, num_epochs=50)
            model = trainer.model
        
        # 评估
        model.eval()
        metrics_calculator = ChatterMetrics()
        all_preds = []
        all_targets = []
        
        with torch.no_grad():
            for batch in test_loader:
                x, y_true, _ = batch
                x = x.to(config.model.device)
                y_pred, _ = model(x) if model_name == "CT-LTC" else (model(x), None)
                all_preds.append(y_pred.cpu().numpy())
                all_targets.append(y_true.numpy())
        
        all_preds = np.concatenate(all_preds, axis=0)
        all_targets = np.concatenate(all_targets, axis=0)
        
        metrics = metrics_calculator.compute_all(all_preds, all_targets)
        results[model_name] = metrics
        
        print(f"\n{model_name} 评估结果:")
        for metric_name, value in metrics.items():
            print(f"  {metric_name}: {value:.4f}")
    
    return results


def run_all_experiments(config) -> Dict[str, Dict[str, Dict[str, float]]]:
    """
    运行所有实验
    
    Args:
        config: 实验配置
    
    Returns:
        所有实验结果
    """
    all_results = {}
    
    # 实验1: 合成数据集
    print("\n" + "="*80)
    print("实验1: 合成数据集 (Synthetic)")
    print("="*80)
    
    synthetic_results = run_single_dataset_experiment(
        config,
        "Synthetic",
        SyntheticChatterDataset,
        {
            "num_samples": 1000,
            "spindle_speed_range": (1000, 10000),
            "axial_depth_range": (0.1, 10.0),
            "noise_level": 0.02
        }
    )
    all_results["Synthetic"] = synthetic_results
    
    # 实验2: 工业数据集
    print("\n" + "="*80)
    print("实验2: 工业数据集 (Industrial)")
    print("="*80)
    
    industrial_results = run_single_dataset_experiment(
        config,
        "Industrial",
        IndustrialChatterDataset,
        {
            "num_samples": 500,
            "num_conditions": 30,
            "material": "6061-T6"
        }
    )
    all_results["Industrial"] = industrial_results
    
    # 保存结果
    results_path = os.path.join(config.output_dir, "all_experiments_results.json")
    
    # 转换结果为可序列化格式
    serializable_results = {}
    for dataset_name, dataset_results in all_results.items():
        serializable_results[dataset_name] = {}
        for model_name, metrics in dataset_results.items():
            serializable_results[dataset_name][model_name] = {
                k: float(v) for k, v in metrics.items()
            }
    
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*80}")
    print(f"所有实验完成！")
    print(f"结果保存至: {results_path}")
    print(f"{'='*80}\n")
    
    return all_results


def print_final_summary(all_results: Dict[str, Dict[str, Dict[str, float]]]):
    """
    打印最终汇总结果
    """
    print("\n" + "="*100)
    print("最终实验结果汇总")
    print("="*100)
    
    for dataset_name, dataset_results in all_results.items():
        print(f"\n数据集: {dataset_name}")
        print("-" * 100)
        print(f"{'模型':<15} {'MAE':>10} {'RMSE':>10} {'R2':>10} {'MAPE':>10}")
        print("-" * 100)
        for model_name, metrics in dataset_results.items():
            print(f"{model_name:<15} {metrics.get('mae',0):>10.4f} {metrics.get('rmse',0):>10.4f} {metrics.get('r2',0):>10.4f} {metrics.get('mape',0):>10.4f}")
        
        best_model = min(dataset_results.items(), key=lambda x: x[1].get('mae', float('inf')))
        print(f"\n最佳模型: {best_model[0]} (MAE: {best_model[1]['mae']:.4f})")
    
    print("\n" + "="*100)


def generate_paper_tables(all_results: Dict[str, Dict[str, Dict[str, float]]]):
    """
    生成论文表格数据
    """
    print("\n" + "="*100)
    print("论文表格数据")
    print("="*100)
    
    # 表2: 主实验结果（2个数据集 × 5种方法）
    print("\n表2: 不同方法在数据集上的MAE对比 (mm)")
    print("-" * 100)
    
    datasets = list(all_results.keys())
    models = list(all_results[datasets[0]].keys())
    
    # 打印表头
    header = "方法"
    for dataset in datasets:
        header += f" & {dataset}"
    header += " & 平均MAE"
    print(header)
    print("-" * 100)
    
    # 打印每个模型的结果
    for model in models:
        row = model
        mae_sum = 0
        
        for dataset in datasets:
            mae = all_results[dataset][model].get('mae', 0)
            row += f" & {mae:.3f}"
            mae_sum += mae
        
        avg_mae = mae_sum / len(datasets)
        row += f" & {avg_mae:.3f}"
        print(row)
    
    print("=" * 100)


if __name__ == "__main__":
    # 获取配置
    config = get_config("main_experiment")
    
    # 设置为CPU（如果有GPU可以改为"cuda"）
    config.model.device = "cpu"
    
    # 减少训练轮数用于快速测试
    config.model.num_epochs_stage1 = 20
    config.model.num_epochs_stage2 = 30
    
    print("开始运行主实验...")
    print(f"设备: {config.model.device}")
    print(f"阶段一轮数: {config.model.num_epochs_stage1}")
    print(f"阶段二轮数: {config.model.num_epochs_stage2}")
    
    # 运行所有实验
    start_time = time.time()
    all_results = run_all_experiments(config)
    end_time = time.time()
    
    print(f"\n总耗时: {(end_time - start_time) / 60:.2f} 分钟")
    
    # 打印汇总结果
    print_final_summary(all_results)
    
    # 生成论文表格
    generate_paper_tables(all_results)
    
    print("\n实验全部完成！")
