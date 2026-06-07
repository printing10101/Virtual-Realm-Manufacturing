"""Cross-modal embedding alignment via contrastive learning.

Implements the contrastive alignment strategy that ensures different modalities
(LLM text, LNN states, JEPA visual) map to semantically consistent positions
in the unified 512-dimensional embedding space.

Core algorithms:
    1. Cross-modal triplet loss with hard negative mining
    2. InfoNCE-based contrastive loss for batch-level alignment
    3. Dynamic temperature scaling for adaptive gradient flow
    4. Incremental embedding update with space compatibility preservation
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from app.ai.unified_embedding.space import (
    get_embedding_space,
)

logger = logging.getLogger(__name__)


@dataclass
class TripletLossConfig:
    """Configuration for triplet loss-based cross-modal alignment.

    The triplet loss ensures that embeddings of the same manufacturing concept
    from different modalities are closer than embeddings of different concepts.

    Loss: L = max(0, d(anchor, positive) - d(anchor, negative) + margin)
    """

    margin: float = 0.3
    p: float = 2.0
    swap: bool = True
    reduction: str = "mean"
    hard_negative_mining: bool = True
    hard_negative_ratio: float = 0.3


@dataclass
class ContrastiveConfig:
    """Configuration for InfoNCE-based contrastive alignment.

    Loss: L = -log( exp(sim(a, p) / tau) / sum(exp(sim(a, n_i) / tau)) )

    where tau is the temperature parameter controlling the concentration
    of the similarity distribution.
    """

    temperature: float = 0.07
    temperature_trainable: bool = True
    temperature_min: float = 0.01
    temperature_max: float = 1.0
    normalize_embeddings: bool = True
    symmetric: bool = True


@dataclass
class AlignerConfig:
    """Full configuration for embedding alignment."""

    triplet: TripletLossConfig = field(default_factory=TripletLossConfig)
    contrastive: ContrastiveConfig = field(default_factory=ContrastiveConfig)
    alignment_weight: float = 0.6
    preservation_weight: float = 0.2
    regularization_weight: float = 0.2
    learning_rate: float = 1e-4
    batch_size: int = 128
    gradient_clip_norm: float = 1.0
    update_interval_steps: int = 100
    compatibility_threshold: float = 0.95


class EmbeddingAligner(ABC):
    """Abstract base class for embedding alignment strategies."""

    def __init__(self, config: AlignerConfig):
        self.config = config
        self._space = get_embedding_space()
        self._iteration: int = 0
        self._loss_history: List[float] = []

    @abstractmethod
    def compute_loss(
        self,
        anchor_embeddings: np.ndarray,
        positive_embeddings: np.ndarray,
        negative_embeddings: Optional[np.ndarray] = None,
    ) -> Tuple[float, Dict[str, float]]:
        pass

    @abstractmethod
    def align(
        self,
        source_modality: str,
        target_modality: str,
        source_embeddings: np.ndarray,
        target_embeddings: np.ndarray,
    ) -> Dict[str, float]:
        pass

    def get_loss_history(self) -> List[float]:
        return self._loss_history


class ContrastiveAligner:
    """Contrastive learning-based cross-modal alignment with InfoNCE loss.

    Implements:

    L_InfoNCE = -1/(2N) * sum_i [ log(exp(sim(z_i^A, z_i^B)/τ) / Σ_j exp(sim(z_i^A, z_j^B)/τ))
                                 + log(exp(sim(z_i^B, z_i^A)/τ) / Σ_j exp(sim(z_i^B, z_j^A)/τ)) ]

    where:
        z_i^A, z_i^B are embeddings of the same concept from modalities A and B
        τ is the temperature parameter
        N is the batch size

    Additionally implements:
        - Cross-modal triplet loss for fine-grained alignment
        - Space preservation regularization
        - Dynamic temperature adjustment
        - Incremental update compatibility check
    """

    def __init__(self, config: Optional[AlignerConfig] = None):
        self.config = config or AlignerConfig()
        self._space = get_embedding_space()
        self._iteration: int = 0
        self._loss_history: List[float] = []
        self._temperature = self.config.contrastive.temperature
        self._compatibility_scores: List[float] = []

    def compute_similarity_matrix(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
        return np.dot(a_norm, b_norm.T)

    def compute_infonce_loss(
        self,
        embeddings_a: np.ndarray,
        embeddings_b: np.ndarray,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute symmetric InfoNCE contrastive loss.

        Args:
            embeddings_a: (batch_size, 512) embeddings from modality A
            embeddings_b: (batch_size, 512) embeddings from modality B

        Returns:
            (loss, metrics) where metrics includes alignment_score and uniformity
        """
        batch_size = embeddings_a.shape[0]

        sim_matrix = self.compute_similarity_matrix(embeddings_a, embeddings_b)
        sim_matrix = sim_matrix / self._temperature

        exp_sim = np.exp(sim_matrix)

        loss_a_to_b = 0.0
        for i in range(batch_size):
            pos_sim = sim_matrix[i, i]
            all_sim_sum = exp_sim[i].sum()
            loss_a_to_b += -pos_sim + np.log(all_sim_sum)
        loss_a_to_b = loss_a_to_b / batch_size

        if self.config.contrastive.symmetric:
            sim_matrix_t = sim_matrix.T
            exp_sim_t = np.exp(sim_matrix_t)
            loss_b_to_a = 0.0
            for i in range(batch_size):
                pos_sim = sim_matrix_t[i, i]
                all_sim_sum = exp_sim_t[i].sum()
                loss_b_to_a += -pos_sim + np.log(all_sim_sum)
            loss_b_to_a = loss_b_to_a / batch_size
            total_loss = (loss_a_to_b + loss_b_to_a) / 2.0
        else:
            total_loss = loss_a_to_b

        alignment_score = self._compute_alignment_score(embeddings_a, embeddings_b)
        uniformity = self._compute_uniformity(embeddings_a, embeddings_b)

        metrics = {
            "infonce_loss": float(total_loss),
            "alignment_score": float(alignment_score),
            "uniformity": float(uniformity),
            "temperature": float(self._temperature),
        }
        self._loss_history.append(float(total_loss))

        return float(total_loss), metrics

    def compute_triplet_loss(
        self,
        anchor: np.ndarray,
        positive: np.ndarray,
        negative: np.ndarray,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute cross-modal triplet loss with optional hard negative mining.

        L_triplet(a, p, n) = max(0, ||a - p||_2 - ||a - n||_2 + margin)

        Args:
            anchor: (batch_size, 512) anchor embeddings
            positive: (batch_size, 512) positive pair embeddings
            negative: (batch_size, 512) or (batch_size, num_negatives, 512)

        Returns:
            (loss, metrics) with positive_distance, negative_distance, margin
        """
        cfg = self.config.triplet
        batch_size = anchor.shape[0]

        d_pos = np.linalg.norm(anchor - positive, axis=1)

        if negative.ndim == 3:
            num_negatives = negative.shape[1]
            d_neg_all = np.zeros((batch_size, num_negatives))
            for j in range(num_negatives):
                d_neg_all[:, j] = np.linalg.norm(anchor - negative[:, j, :], axis=1)

            if cfg.hard_negative_mining:
                n_hard = max(1, int(num_negatives * cfg.hard_negative_ratio))
                d_neg = np.partition(d_neg_all, n_hard - 1, axis=1)[:, :n_hard].mean(axis=1)
            else:
                d_neg = d_neg_all.min(axis=1)
        else:
            d_neg = np.linalg.norm(anchor - negative, axis=1)

        losses = np.maximum(0, d_pos - d_neg + cfg.margin)

        if cfg.reduction == "mean":
            loss = float(losses.mean())
        elif cfg.reduction == "sum":
            loss = float(losses.sum())
        else:
            loss = float(losses.mean())

        metrics = {
            "triplet_loss": loss,
            "mean_positive_distance": float(d_pos.mean()),
            "mean_negative_distance": float(d_neg.mean()),
            "margin": cfg.margin,
            "hard_triplet_ratio": float((losses > 0).mean()),
        }
        self._loss_history.append(loss)

        return loss, metrics

    def compute_preservation_loss(
        self,
        original_embeddings: np.ndarray,
        updated_embeddings: np.ndarray,
    ) -> Tuple[float, float]:
        """Compute space preservation loss for incremental updates.

        Ensures updated embeddings remain compatible with the original space.
        L_preservation = 1 - cosine_similarity(original, updated)
        """
        original_norm = original_embeddings / (np.linalg.norm(original_embeddings, axis=1, keepdims=True) + 1e-10)
        updated_norm = updated_embeddings / (np.linalg.norm(updated_embeddings, axis=1, keepdims=True) + 1e-10)
        similarities = np.sum(original_norm * updated_norm, axis=1)
        loss = float(1.0 - similarities.mean())
        compatibility = float(similarities.mean())
        self._compatibility_scores.append(compatibility)
        return loss, compatibility

    def compute_total_loss(
        self,
        embeddings_a: np.ndarray,
        embeddings_b: np.ndarray,
        negative_embeddings: Optional[np.ndarray] = None,
        original_embeddings: Optional[np.ndarray] = None,
        updated_embeddings: Optional[np.ndarray] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """Compute combined alignment loss with all components.

        L_total = w_align * L_infoNCE + w_preserve * L_preservation + w_reg * L_reg

        Args:
            embeddings_a: (batch_size, 512) from modality A
            embeddings_b: (batch_size, 512) from modality B
            negative_embeddings: Optional negative samples for triplet loss
            original_embeddings: Original embeddings before update
            updated_embeddings: Updated embeddings after alignment

        Returns:
            (total_loss, component_metrics)
        """
        cfg = self.config

        infonce_loss, infonce_metrics = self.compute_infonce_loss(embeddings_a, embeddings_b)
        total_loss = cfg.alignment_weight * infonce_loss
        metrics = {f"infonce_{k}": v for k, v in infonce_metrics.items()}

        if negative_embeddings is not None:
            triplet_loss, triplet_metrics = self.compute_triplet_loss(
                embeddings_a, embeddings_b, negative_embeddings
            )
            total_loss += cfg.alignment_weight * 0.3 * triplet_loss
            metrics.update({f"triplet_{k}": v for k, v in triplet_metrics.items()})

        if original_embeddings is not None and updated_embeddings is not None:
            preserve_loss, compatibility = self.compute_preservation_loss(
                original_embeddings, updated_embeddings
            )
            total_loss += cfg.preservation_weight * preserve_loss
            metrics.update({
                "preservation_loss": preserve_loss,
                "compatibility": compatibility,
            })

        metrics["total_loss"] = float(total_loss)

        return float(total_loss), metrics

    def align(
        self,
        source_modality: str,
        target_modality: str,
        source_embeddings: np.ndarray,
        target_embeddings: np.ndarray,
        learning_rate: Optional[float] = None,
    ) -> Dict[str, float]:
        """Perform one alignment step between two modalities.

        Uses gradient-based optimization to minimize the contrastive loss
        by adjusting embedding positions in the unified space.

        Args:
            source_modality: Name of source modality (e.g., "llm")
            target_modality: Name of target modality (e.g., "lnn")
            source_embeddings: (batch_size, 512) from source
            target_embeddings: (batch_size, 512) from target
            learning_rate: Step size for gradient update

        Returns:
            Metrics dictionary with loss, alignment_score, compatibility
        """
        lr = learning_rate or self.config.learning_rate
        batch_size = source_embeddings.shape[0]

        sim_matrix = self.compute_similarity_matrix(source_embeddings, target_embeddings)
        sim_matrix = sim_matrix / self._temperature

        exp_sim = np.exp(sim_matrix)

        grad_source = np.zeros_like(source_embeddings)
        grad_target = np.zeros_like(target_embeddings)

        source_norm = source_embeddings / (np.linalg.norm(source_embeddings, axis=1, keepdims=True) + 1e-10)
        target_norm = target_embeddings / (np.linalg.norm(target_embeddings, axis=1, keepdims=True) + 1e-10)

        for i in range(batch_size):
            pos_weight = 1.0 / self._temperature
            grad_source[i] = -pos_weight * target_norm[i]
            grad_target[i] = -pos_weight * source_norm[i]

            sum_exp = exp_sim[i].sum()
            for j in range(batch_size):
                weight = exp_sim[i, j] / (sum_exp * self._temperature)
                grad_source[i] = grad_source[i] + weight * target_norm[j]
                if self.config.contrastive.symmetric:
                    grad_target[j] = grad_target[j] + weight * source_norm[i]

        grad_source = grad_source / batch_size
        grad_target = grad_target / batch_size

        grad_norm_s = np.linalg.norm(grad_source)
        grad_norm_t = np.linalg.norm(grad_target)
        max_norm = self.config.gradient_clip_norm

        if grad_norm_s > max_norm:
            grad_source = grad_source * (max_norm / grad_norm_s)
        if grad_norm_t > max_norm:
            grad_target = grad_target * (max_norm / grad_norm_t)

        original_source = source_embeddings.copy()

        updated_source = source_embeddings - lr * grad_source
        updated_target = target_embeddings - lr * grad_target

        updated_source = self._space.normalize(updated_source)
        updated_target = self._space.normalize(updated_target)

        loss, metrics = self.compute_total_loss(
            updated_source, updated_target,
            original_embeddings=original_source.copy(),
            updated_embeddings=updated_source.copy(),
        )

        preserve_loss, compatibility = self.compute_preservation_loss(
            original_source, updated_source
        )
        metrics["compatibility"] = float(compatibility)

        self._iteration += 1
        self._update_temperature()

        logger.debug(
            "Align step %d: %s->%s, loss=%.4f, compat=%.4f, temp=%.4f",
            self._iteration, source_modality, target_modality,
            loss, compatibility, self._temperature,
        )

        return metrics

    def cross_modal_align(
        self,
        llm_embeddings: np.ndarray,
        lnn_embeddings: np.ndarray,
        jepa_embeddings: Optional[np.ndarray] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Perform full cross-modal alignment across all three modalities.

        Args:
            llm_embeddings: (batch_size, 512) LLM embeddings
            lnn_embeddings: (batch_size, 512) LNN embeddings
            jepa_embeddings: Optional (batch_size, 512) JEPA embeddings

        Returns:
            Dictionary mapping modality pairs to their alignment metrics
        """
        results = {}

        results["llm-lnn"] = self.align("llm", "lnn", llm_embeddings, lnn_embeddings)

        if jepa_embeddings is not None:
            results["llm-jepa"] = self.align("llm", "jepa", llm_embeddings, jepa_embeddings)
            results["lnn-jepa"] = self.align("lnn", "jepa", lnn_embeddings, jepa_embeddings)

        return results

    def _compute_alignment_score(self, a: np.ndarray, b: np.ndarray) -> float:
        sim = self.compute_similarity_matrix(a, b)
        batch_size = a.shape[0]
        if batch_size == 0:
            return 0.0
        diag_sim = np.diag(sim)
        return float(diag_sim.mean())

    def _compute_uniformity(
        self,
        a: np.ndarray,
        b: np.ndarray,
        t: float = 2.0,
    ) -> float:
        combined = np.concatenate([a, b], axis=0)
        n = combined.shape[0]
        if n <= 1:
            return 0.0
        norms = combined / (np.linalg.norm(combined, axis=1, keepdims=True) + 1e-10)
        sim = np.dot(norms, norms.T)
        uniformity = np.exp(-t * sim).sum() / (n * (n - 1))
        return float(-np.log(uniformity + 1e-10))

    def _update_temperature(self):
        if not self.config.contrastive.temperature_trainable:
            return
        if self._iteration % 10 == 0 and len(self._loss_history) >= 2:
            recent_loss = np.mean(self._loss_history[-10:])
            earlier_loss = np.mean(
                self._loss_history[max(0, len(self._loss_history) - 20):len(self._loss_history) - 10]
            )
            if recent_loss < earlier_loss * 0.95:
                self._temperature = max(
                    self.config.contrastive.temperature_min,
                    self._temperature * 0.95,
                )

    def check_compatibility(self) -> bool:
        if len(self._compatibility_scores) < 10:
            return True
        recent_compat = np.mean(self._compatibility_scores[-10:])
        return recent_compat >= self.config.compatibility_threshold

    def get_stats(self) -> Dict[str, float]:
        return {
            "total_iterations": self._iteration,
            "current_temperature": self._temperature,
            "mean_loss": float(np.mean(self._loss_history[-100:])) if self._loss_history else 0.0,
            "recent_compatibility": float(np.mean(self._compatibility_scores[-10:]))
            if self._compatibility_scores else 1.0,
            "compatibility_check": float(self.check_compatibility()),
        }
