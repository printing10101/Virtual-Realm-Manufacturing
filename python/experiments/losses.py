"""
物理损失函数模块
实现PCC Loss等物理约束损失
"""

import torch
import torch.nn as nn
import torch.autograd as autograd
from typing import Optional, Tuple
import numpy as np


class PCC_Loss(nn.Module):
    """
    物理一致性损失 (Physics-Consistency Loss)
    包含数值层和梯度层双重约束
    """
    
    def __init__(
        self,
        epsilon_phys: float = 0.05,
        lambda_phys: float = 0.5,
        lambda_pcc: float = 0.1
    ):
        """
        初始化PCC损失
        
        Args:
            epsilon_phys: 物理容忍阈值 (mm)
            lambda_phys: 物理损失权重
            lambda_pcc: 梯度一致性损失权重
        """
        super().__init__()
        
        self.epsilon_phys = epsilon_phys
        self.lambda_phys = lambda_phys
        self.lambda_pcc = lambda_pcc
    
    def forward(
        self,
        y_pred: torch.Tensor,
        y_true: torch.Tensor,
        y_physics: torch.Tensor,
        x: torch.Tensor,
        model: nn.Module
    ) -> Tuple[torch.Tensor, dict]:
        """
        计算PCC损失
        
        Args:
            y_pred: 模型预测 [batch_size, output_dim]
            y_true: 真实标签 [batch_size, output_dim]
            y_physics: 物理模型预测 [batch_size, output_dim]
            x: 输入特征 [batch_size, input_dim]
            model: 神经网络模型
        
        Returns:
            total_loss: 总损失
            loss_dict: 各项损失字典
        """
        # 数据损失 (MAE)
        loss_data = torch.mean(torch.abs(y_pred - y_true))
        
        # 物理损失 (数值层)
        # L_phys = max(0, |y_pred - y_physics| - epsilon)
        phys_diff = torch.abs(y_pred - y_physics)
        loss_phys = torch.mean(torch.clamp(phys_diff - self.epsilon_phys, min=0.0))
        
        # 梯度一致性损失 (梯度层)
        loss_pcc = self._compute_gradient_loss(y_pred, y_physics, x, model)
        
        # 总损失
        total_loss = (
            1.0 * loss_data +
            self.lambda_phys * loss_phys +
            self.lambda_pcc * loss_pcc
        )
        
        loss_dict = {
            'total': total_loss.item(),
            'data': loss_data.item(),
            'phys': loss_phys.item(),
            'pcc': loss_pcc.item()
        }
        
        return total_loss, loss_dict
    
    def _compute_gradient_loss(
        self,
        y_pred: torch.Tensor,
        y_physics: torch.Tensor,
        x: torch.Tensor,
        model: nn.Module
    ) -> torch.Tensor:
        """
        计算梯度一致性损失
        
        Args:
            y_pred: 模型预测
            y_physics: 物理模型预测
            x: 输入特征
            model: 神经网络模型
        
        Returns:
            梯度损失
        """
        batch_size = x.size(0)
        
        # 计算预测梯度（模型预测对输入的梯度）
        grad_pred = autograd.grad(
            outputs=y_pred.sum(),
            inputs=x,
            create_graph=True,
            retain_graph=True
        )[0]
        
        # 简化的物理约束：梯度应该与物理预测的相对大小一致
        # 使用 y_physics 作为权重，而不是计算其梯度
        # 物理意义：当物理预测值较大时，模型预测的梯度也应该较大
        grad_magnitude = torch.norm(grad_pred, dim=1, keepdim=True)
        physics_magnitude = torch.norm(y_physics, dim=1, keepdim=True)
        
        # 归一化
        grad_magnitude_norm = grad_magnitude / (grad_magnitude.max() + 1e-8)
        physics_magnitude_norm = physics_magnitude / (physics_magnitude.max() + 1e-8)
        
        # 梯度幅度与物理预测的一致性
        loss_pcc = torch.mean(torch.abs(grad_magnitude_norm - physics_magnitude_norm))
        
        return loss_pcc


class PhysicsLoss(nn.Module):
    """
    纯物理损失（无数值层）
    """
    
    def __init__(self, epsilon_phys: float = 0.05):
        super().__init__()
        self.epsilon_phys = epsilon_phys
    
    def forward(
        self,
        y_pred: torch.Tensor,
        y_physics: torch.Tensor
    ) -> torch.Tensor:
        """
        计算物理损失
        
        Args:
            y_pred: 模型预测
            y_physics: 物理模型预测
        
        Returns:
            物理损失
        """
        phys_diff = torch.abs(y_pred - y_physics)
        loss = torch.mean(torch.clamp(phys_diff - self.epsilon_phys, min=0.0))
        return loss


class GradientLoss(nn.Module):
    """
    纯梯度损失
    """
    
    def __init__(self):
        super().__init__()
    
    def forward(
        self,
        y_pred: torch.Tensor,
        y_physics: torch.Tensor,
        x: torch.Tensor,
        model: nn.Module
    ) -> torch.Tensor:
        """
        计算梯度损失
        
        Args:
            y_pred: 模型预测
            y_physics: 物理模型预测
            x: 输入特征
            model: 神经网络模型
        
        Returns:
            梯度损失
        """
        # 计算预测梯度
        grad_pred = autograd.grad(
            outputs=y_pred.sum(),
            inputs=x,
            create_graph=True,
            retain_graph=True
        )[0]
        
        # 计算物理梯度
        grad_physics = autograd.grad(
            outputs=y_physics.sum(),
            inputs=x,
            create_graph=True,
            retain_graph=True
        )[0]
        
        # 梯度差异
        grad_diff = torch.abs(grad_pred - grad_physics)
        loss = torch.mean(grad_diff)
        
        return loss


class StabilityLoss(nn.Module):
    """
    稳定性分类损失
    用于预测稳定性标签（稳定/不稳定）
    """
    
    def __init__(self):
        super().__init__()
        self.bce = nn.BCEWithLogitsLoss()
    
    def forward(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor
    ) -> torch.Tensor:
        """
        计算稳定性损失
        
        Args:
            logits: 模型输出logits [batch_size, 1]
            labels: 真实标签 [batch_size, 1]
        
        Returns:
            损失
        """
        return self.bce(logits, labels)


class CombinedLoss(nn.Module):
    """
    组合损失函数
    结合回归损失和分类损失
    """
    
    def __init__(
        self,
        lambda_reg: float = 1.0,
        lambda_cls: float = 0.5,
        lambda_phys: float = 0.5,
        lambda_pcc: float = 0.1,
        epsilon_phys: float = 0.05
    ):
        """
        初始化组合损失
        
        Args:
            lambda_reg: 回归损失权重
            lambda_cls: 分类损失权重
            lambda_phys: 物理损失权重
            lambda_pcc: 梯度损失权重
            epsilon_phys: 物理阈值
        """
        super().__init__()
        
        self.lambda_reg = lambda_reg
        self.lambda_cls = lambda_cls
        self.lambda_phys = lambda_phys
        self.lambda_pcc = lambda_pcc
        
        self.pcc_loss = PCC_Loss(
            epsilon_phys=epsilon_phys,
            lambda_phys=lambda_phys,
            lambda_pcc=lambda_pcc
        )
        
        self.stability_loss = StabilityLoss()
    
    def forward(
        self,
        y_pred_reg: torch.Tensor,
        y_true_reg: torch.Tensor,
        y_physics: torch.Tensor,
        y_pred_cls: torch.Tensor,
        y_true_cls: torch.Tensor,
        x: torch.Tensor,
        model: nn.Module
    ) -> Tuple[torch.Tensor, dict]:
        """
        计算组合损失
        
        Args:
            y_pred_reg: 回归预测
            y_true_reg: 回归真实值
            y_physics: 物理预测
            y_pred_cls: 分类预测
            y_true_cls: 分类真实值
            x: 输入特征
            model: 模型
        
        Returns:
            total_loss: 总损失
            loss_dict: 损失字典
        """
        # 回归损失（含物理约束）
        loss_reg, reg_dict = self.pcc_loss(
            y_pred_reg, y_true_reg, y_physics, x, model
        )
        
        # 分类损失
        loss_cls = self.stability_loss(y_pred_cls, y_true_cls)
        
        # 总损失
        total_loss = self.lambda_reg * loss_reg + self.lambda_cls * loss_cls
        
        loss_dict = {
            'total': total_loss.item(),
            'reg_total': reg_dict['total'],
            'reg_data': reg_dict['data'],
            'reg_phys': reg_dict['phys'],
            'reg_pcc': reg_dict['pcc'],
            'cls': loss_cls.item()
        }
        
        return total_loss, loss_dict


if __name__ == "__main__":
    # 测试损失函数
    print("测试PCC损失...")
    
    pcc_loss = PCC_Loss(epsilon_phys=0.05, lambda_phys=0.5, lambda_pcc=0.1)
    
    # 创建测试数据
    batch_size = 32
    input_dim = 2
    output_dim = 1
    
    x = torch.randn(batch_size, input_dim, requires_grad=True)
    y_pred = torch.randn(batch_size, output_dim, requires_grad=True)
    y_true = torch.randn(batch_size, output_dim)
    y_physics = torch.randn(batch_size, output_dim)
    
    # 创建简单模型
    model = nn.Linear(input_dim, output_dim)
    
    # 计算损失
    total_loss, loss_dict = pcc_loss(y_pred, y_true, y_physics, x, model)
    
    print(f"总损失: {total_loss.item():.4f}")
    print(f"数据损失: {loss_dict['data']:.4f}")
    print(f"物理损失: {loss_dict['phys']:.4f}")
    print(f"PCC损失: {loss_dict['pcc']:.4f}")
    
    print("\n损失函数测试通过！")
