"""
多模态数据融合模块

将不同数据源的提取特征融合为统一特征表示，支持：
- 简单加权融合
- 交叉模态注意力融合
- 可学习融合权重
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from app.data.pipeline.config import FusionConfig

logger = logging.getLogger(__name__)

# M7 配套：训练/推理模式标志。
# True 时 CrossModalAttentionFusion 的 dropout 生效（随机置零 + 缩放）；
# False 时 dropout 不操作（推理模式）。
# 由训练入口在训练前设置为 True，训练结束后恢复 False。
_FUSION_TRAINING = False


def set_fusion_training_mode(training: bool) -> None:
    """设置融合模块的训练/推理模式。

    训练入口应在训练前调用 set_fusion_training_mode(True)，
    训练结束或异常退出时调用 set_fusion_training_mode(False)。
    """
    global _FUSION_TRAINING
    _FUSION_TRAINING = training


class MultiModalFusion:
    """
    简单加权多模态融合

    基于预定义权重对各模态特征进行加权平均融合。
    """

    def __init__(self, config: FusionConfig):
        self.config = config
        self.weights = config.modality_weights.copy()
        self._normalize_weights()

    def _normalize_weights(self):
        """归一化权重总和为1"""
        total = sum(self.weights.values())
        if total > 0:
            for k in self.weights:
                self.weights[k] /= total

    def set_weights(self, new_weights: Dict[str, float]):
        """更新融合权重"""
        self.weights.update(new_weights)
        self._normalize_weights()

    def fuse(
        self,
        features: Dict[str, np.ndarray],
        weights: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        融合多模态特征

        Args:
            features: {modality: feature_vector} 字典
            weights: 可选覆盖权重

        Returns:
            融合后的特征向量
        """
        if weights is None:
            weights = self.weights

        if not features:
            raise ValueError("特征字典为空，无法融合")

        first_dim = next(iter(features.values())).shape[-1]
        weighted_sum = np.zeros(first_dim, dtype=np.float32)
        total_weight = 0.0

        for modality, feat in features.items():
            w = weights.get(modality, 1.0 / len(features))
            if feat.ndim > 1:
                feat = feat.flatten()

            if feat.size != first_dim and feat.size != 1:
                target_size = weighted_sum.shape[0]
                if feat.size < target_size:
                    feat = np.pad(feat, (0, target_size - feat.size), mode="constant")
                else:
                    feat = feat[:target_size]

            weighted_sum += w * feat
            total_weight += w

        if total_weight > 0:
            fused = weighted_sum / total_weight
        else:
            fused = weighted_sum

        norm = np.linalg.norm(fused)
        if norm > 0:
            fused = fused / norm

        return fused

    def fuse_batch(
        self,
        features_dict: Dict[str, List[np.ndarray]],
        weights: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """批量融合"""
        if weights is None:
            weights = self.weights

        n_samples = len(next(iter(features_dict.values())))
        first = next(iter(features_dict.values()))[0]
        dim = first.shape[-1] if first.ndim > 0 else 1

        result = np.zeros((n_samples, self.config.target_dim if self.config else dim), dtype=np.float32)

        for i in range(n_samples):
            batch_features = {modality: features[i] for modality, features in features_dict.items()}
            result[i] = self.fuse(batch_features, weights)

        return result


class CrossModalAttentionFusion:
    """
    交叉模态注意力融合（权重未经训练，占位实现）

    P1 学术诚信警告：
        本模块的投影权重为随机初始化，未经过训练，融合结果不具备物理意义。
        生产环境或学术论文实验必须从训练 checkpoint 加载权重，否则跨模态
        融合结果不可信（项目目标期刊：Journal of Intelligent Manufacturing）。

    使用注意力机制学习各模态特征的权重，支持多头注意力。
    """

    def __init__(self, config: FusionConfig):
        self.config = config
        self.n_heads = config.attention_heads
        self.dropout = config.dropout
        self.target_dim = config.target_dim
        self._projections = None
        self._output_proj = None
        self._initialized = False

        # P1 学术诚信修复：移除 np.random.seed(42) 全局污染（影响其他模块的随机性），
        # 改用局部 Generator。注意：权重仍为随机初始化，见类 docstring 警告。
        self._rng = np.random.default_rng(42)

    def _init_weights(self, input_dims: Dict[str, int]):
        """初始化投影权重（随机占位，未经训练）"""
        d_k = self.target_dim // self.n_heads
        self._projections = {}
        for modality, in_dim in input_dims.items():
            proj_k = self._rng.standard_normal((in_dim, d_k)) / np.sqrt(in_dim)
            proj_v = self._rng.standard_normal((in_dim, d_k)) / np.sqrt(in_dim)
            proj_q = self._rng.standard_normal((in_dim, d_k)) / np.sqrt(in_dim)
            self._projections[modality] = (proj_q, proj_k, proj_v)

        self._output_proj = self._rng.standard_normal((self.n_heads * d_k, self.target_dim)) / np.sqrt(
            self.n_heads * d_k
        )
        self._initialized = True
        logger.warning(
            "CrossModalAttentionFusion 使用随机占位权重（未经训练），融合结果不具备物理意义，禁止用于生产或学术论文实验"
        )

    def _attention(self, q: np.ndarray, k: np.ndarray, v: np.ndarray) -> np.ndarray:
        """缩放点积注意力"""
        d_k = q.shape[-1]
        scores = np.dot(q, k.T) / np.sqrt(d_k)
        exp_scores = np.exp(scores - np.max(scores))
        attn = exp_scores / (np.sum(exp_scores, axis=-1, keepdims=True) + 1e-10)
        # M7 bug 修复：原代码 `attn = (1 - self.dropout) * attn` 是确定性缩放，
        # 不是真正的 dropout（没有任何正则化效果，只是降低注意力权重）。
        # 真正的 dropout 应在训练时随机置零 + 缩放，推理时不操作。
        # numpy 无内置 training 标志，这里用模块级 _FUSION_TRAINING 标志控制。
        if self.dropout > 0 and _FUSION_TRAINING:
            mask = (np.random.rand(*attn.shape) > self.dropout).astype(attn.dtype)
            attn = attn * mask / (1.0 - self.dropout)
        return np.dot(attn, v)

    def fuse(
        self,
        features: Dict[str, np.ndarray],
        attention_mask: Optional[Dict[str, bool]] = None,
    ) -> np.ndarray:
        """
        交叉模态注意力融合

        Args:
            features: {modality: feature_vector} 字典
            attention_mask: 可选掩码，表示哪些模态是有效的

        Returns:
            融合后的特征向量 (target_dim,)
        """
        if not self._initialized:
            input_dims = {m: f.size for m, f in features.items()}
            self._init_weights(input_dims)

        modalities = list(features.keys())

        outputs = []
        for head in range(self.n_heads):
            head_q, head_k, head_v = [], [], []
            for modality in modalities:
                feat = features[modality]
                if feat.ndim > 1:
                    feat = feat.flatten()
                proj_q, proj_k, proj_v = self._projections[modality]
                q = np.dot(feat, proj_q)
                k = np.dot(feat, proj_k)
                v = np.dot(feat, proj_v)
                head_q.append(q)
                head_k.append(k)
                head_v.append(v)

            q_stack = np.stack(head_q, axis=0)
            k_stack = np.stack(head_k, axis=0)
            v_stack = np.stack(head_v, axis=0)

            out = self._attention(q_stack, k_stack, v_stack)
            outputs.append(out.mean(axis=0))

        concat = np.concatenate(outputs, axis=0)
        if concat.shape[0] != self._output_proj.shape[0]:
            if concat.shape[0] < self._output_proj.shape[0]:
                concat = np.pad(concat, (0, self._output_proj.shape[0] - concat.shape[0]))
            else:
                concat = concat[: self._output_proj.shape[0]]

        fused = np.dot(concat, self._output_proj)
        norm = np.linalg.norm(fused)
        if norm > 0:
            fused = fused / norm

        return fused

    def get_attention_weights(
        self,
        features: Dict[str, np.ndarray],
    ) -> Dict[str, np.ndarray]:
        """提取各模态注意力权重"""
        if not self._initialized or not self._projections:
            return {m: np.array([1.0 / len(features)]) for m in features}

        attn_weights = {}
        for modality, feat in features.items():
            if feat.ndim > 1:
                feat = feat.flatten()
            proj_q, _, _ = self._projections[modality]
            weights = np.abs(proj_q).mean(axis=1)
            attn_weights[modality] = weights / (np.sum(weights) + 1e-10)

        return attn_weights
