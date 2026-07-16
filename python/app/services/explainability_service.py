"""可解释性可视化服务层.

对应 ADR-016（可解释性可视化）。实现 ``IExplainabilityService`` 接口契约，
组合降维投影 / 反事实扫描 / MC dropout 采样 / 载荷持久化，为前端提供
LTC 隐状态投影、门控动力学、反事实解释、置信度分布四类解释能力。

职责
----
1. **隐状态投影**（``hidden_state``）：调用 ``LNNPredictor.predict_with_intermediates``
   捕获隐状态序列，PCA/t-SNE/UMAP 降维到 2D/3D，输出可视化坐标。
2. **门控动力学**（``gate_dynamics``）：从 intermediates 提取门控值与时间常数 τ，
   计算异常帧（``mean ± sigma*std``），输出时序曲线数据。
3. **反事实解释**（``counterfactual``）：扰动单输入特征，逐点推理扫描输出敏感性，
   计算一阶敏感度系数与临界点。
4. **置信度分布**（``confidence``）：调用 ``predict_mc_dropout`` 多次采样，
   计算分位数、直方图、认知/偶然不确定性。

线程安全
--------
- 单例通过双重检查锁创建
- predictor 缓存（LRU limit=4）使用锁保护
- 降维器缓存（按 model_uri）使用锁保护
- DB 写操作通过 SQLAlchemy 事务保证原子性，显式 commit()

错误处理风格（与 ProjectPackageService 对齐）：
- 参数校验失败 → ExplanationValidationError
- 解释记录不存在 → ExplanationLookupError
- 降维失败 → ProjectionError
- MC dropout 采样失败 → SamplingError
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from typing import Any, Optional

import numpy as np
from sqlalchemy import desc, func, select

from app.config import config
from app.contracts.explainability import (
    ComparisonMismatchError,
    ComparisonType,
    ConfidenceExplanation,
    CounterfactualExplanation,
    ExplainabilityError,
    ExplanationComparison,
    ExplanationLookupError,
    ExplanationRecord,
    ExplanationRequest,
    ExplanationType,
    ExplanationValidationError,
    GateDynamicsExplanation,
    HiddenStateExplanation,
    ProjectionError,
    ProjectionMethod,
    SamplingError,
)
from app.database.connection import get_sessionmaker
from app.database.models.explainability import (
    ExplanationComparison as ExplanationComparisonORM,
    ExplanationRecord as ExplanationRecordORM,
    _gen_comparison_id,
    _gen_explanation_id,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------


_service_singleton: Optional["ExplainabilityService"] = None
_service_lock = threading.Lock()


def get_explainability_service() -> "ExplainabilityService":
    """获取 ExplainabilityService 单例（双重检查锁）."""
    global _service_singleton
    if _service_singleton is None:
        with _service_lock:
            if _service_singleton is None:
                _service_singleton = ExplainabilityService()
    return _service_singleton


def reset_explainability_service() -> None:
    """重置单例（仅供测试）."""
    global _service_singleton
    with _service_lock:
        _service_singleton = None


# ---------------------------------------------------------------------------
# 服务实现
# ---------------------------------------------------------------------------


class ExplainabilityService:
    """可解释性服务：实现 ``IExplainabilityService`` 接口.

    内部组合 LNNPredictor（按 model_uri 缓存）+ 降维器（按 model_uri 缓存），
    自身管理 ``explanation_records`` + ``explanation_comparisons`` 两张 ORM 表
    与 payload 文件持久化。

    设计原则
    --------
    - 读操作（get/list）无锁
    - 写操作（generate/delete/compare）通过 DB 事务保证原子性
    - payload 文件以 JSON 存盘，数据库只存元数据 + payload_path
    - 降维器序列化复用，确保同一模型多次解释投影空间一致
    """

    # predictor LRU 缓存上限（与 world_model/plugin.py 对齐）
    _PREDICTOR_CACHE_LIMIT = 4

    def __init__(self) -> None:
        # predictor 缓存：model_uri → LNNPredictor
        self._predictor_cache: dict[str, Any] = {}
        self._predictor_lock = threading.Lock()

        # 降维器缓存：model_uri → (method, reducer)
        self._reducer_cache: dict[str, tuple[str, Any]] = {}
        self._reducer_lock = threading.Lock()

        # payload 存储根目录：<output_dir>/explainability/payloads/
        self._payloads_root = os.path.join(
            os.path.abspath(config.storage.output_dir),
            "explainability",
            "payloads",
        )
        os.makedirs(self._payloads_root, exist_ok=True)

        # 降维器存储目录：<output_dir>/explainability/reducers/
        self._reducers_root = os.path.join(
            os.path.abspath(config.storage.output_dir),
            "explainability",
            "reducers",
        )
        os.makedirs(self._reducers_root, exist_ok=True)

    # ── Session 管理 ──────────────────────────────────────────────────

    async def _get_session(self):
        """获取 AsyncSession（每段独立 commit）."""
        sessionmaker = get_sessionmaker()
        if sessionmaker is None:
            raise RuntimeError("数据库未配置，无法获取 session")
        return sessionmaker()

    # ── 模型加载 ──────────────────────────────────────────────────────

    def _parse_model_uri(self, model_uri: str) -> str:
        """解析 model_uri 为 model_name.

        支持格式：
        - ``model://<model_name>/<version>``
        - ``model://<model_name>``
        - ``<model_name>``（直接使用）

        Returns
        -------
        str
            模型名称（用于 ModelRegistry.get / from_registry）。
        """
        if not model_uri:
            raise ExplanationValidationError("model_uri 不能为空")
        if model_uri.startswith("model://"):
            rest = model_uri[len("model://"):]
            # 去除 version 部分（首个 / 之后）
            if "/" in rest:
                return rest.split("/", 1)[0]
            return rest
        return model_uri

    def _get_predictor(self, model_uri: str):
        """获取或加载 LNNPredictor（LRU 缓存，limit=4）.

        Returns
        -------
        LNNPredictor
            已加载的预测器实例。

        Raises
        ------
        ExplainabilityError
            模型加载失败。
        """
        # 快速路径：缓存命中
        predictor = self._predictor_cache.get(model_uri)
        if predictor is not None:
            return predictor

        with self._predictor_lock:
            predictor = self._predictor_cache.get(model_uri)
            if predictor is not None:
                return predictor

            # 加载模型
            model_name = self._parse_model_uri(model_uri)
            try:
                from app.ai.lnn.inference.predictor import LNNPredictor
                from app.services.model_registry_service import (
                    get_model_registry_service,
                )

                registry = get_model_registry_service().model_registry
                predictor = LNNPredictor.from_registry(registry, model_name)
            except (ImportError, AttributeError, RuntimeError, ValueError) as exc:
                logger.error(
                    "加载模型失败 model_uri=%s: %s",
                    model_uri,
                    exc,
                    exc_info=True,
                )
                raise ProjectionError(
                    f"无法加载模型: {model_uri}（{exc}）"
                ) from exc

            # LRU 淘汰
            if len(self._predictor_cache) >= self._PREDICTOR_CACHE_LIMIT:
                oldest_uri = next(iter(self._predictor_cache))
                del self._predictor_cache[oldest_uri]
            self._predictor_cache[model_uri] = predictor
            return predictor

    # ── 降维投影 ──────────────────────────────────────────────────────

    def _project(
        self,
        method: str,
        data: np.ndarray,
        dim: int,
        model_uri: str,
    ) -> np.ndarray:
        """降维投影（PCA / t-SNE / UMAP）.

        Parameters
        ----------
        method : str
            降维方法（``ProjectionMethod`` 常量）。
        data : np.ndarray
            输入数据 ``[N, hidden_dim]``。
        dim : int
            目标维度（2 或 3）。
        model_uri : str
            模型 URI（用于降维器缓存键）。

        Returns
        -------
        np.ndarray
            降维后坐标 ``[N, dim]``。

        Raises
        ------
        ProjectionError
            降维失败（样本数不足 / 维度不匹配 / 方法不可用）。
        """
        if data.ndim != 2:
            raise ProjectionError(
                f"降维输入必须为 2D 数组 [N, hidden_dim]，当前: {data.shape}"
            )
        n_samples, n_features = data.shape
        if n_samples < 2:
            raise ProjectionError(
                f"降维样本数不足（需要 >=2，当前: {n_samples}）"
            )
        if dim not in (2, 3):
            raise ProjectionError(f"目标维度必须为 2 或 3，当前: {dim}")

        cache_key = f"{model_uri}:{method}:{dim}"

        # PCA：支持 fit + transform，降维器序列化复用
        if method == ProjectionMethod.PCA:
            try:
                from sklearn.decomposition import PCA
            except ImportError as exc:
                raise ProjectionError(
                    "PCA 需要 scikit-learn，请安装: pip install scikit-learn"
                ) from exc

            with self._reducer_lock:
                cached = self._reducer_cache.get(cache_key)
                if cached is not None:
                    _, reducer = cached
                else:
                    n_components = min(dim, n_features, n_samples)
                    if n_components < dim:
                        raise ProjectionError(
                            f"PCA 分量数 {n_components} 小于目标维度 {dim}，"
                            f"请减少 dim 或增加样本数"
                        )
                    reducer = PCA(n_components=n_components)
                    reducer.fit(data)
                    self._reducer_cache[cache_key] = (method, reducer)
            try:
                return reducer.transform(data)[:, :dim]
            except (ValueError, RuntimeError) as exc:
                raise ProjectionError(f"PCA 投影失败: {exc}") from exc

        # t-SNE：无 transform 方法，每次重新拟合（不支持复用）
        if method == ProjectionMethod.TSNE:
            if n_samples > 5000:
                raise ProjectionError(
                    f"t-SNE 样本数限制 <=5000，当前: {n_samples}，"
                    f"请改用 PCA 或下采样"
                )
            try:
                from sklearn.manifold import TSNE
            except ImportError as exc:
                raise ProjectionError(
                    "t-SNE 需要 scikit-learn，请安装: pip install scikit-learn"
                ) from exc

            n_components = min(dim, n_features, n_samples - 1)
            if n_components < dim:
                raise ProjectionError(
                    f"t-SNE 分量数 {n_components} 小于目标维度 {dim}"
                )
            reducer = TSNE(
                n_components=n_components,
                perplexity=min(30.0, max(5.0, n_samples - 1)),
                init="pca",
                learning_rate="auto",
                n_iter=1000,
                random_state=42,
            )
            try:
                result = reducer.fit_transform(data)
                return result[:, :dim]
            except (ValueError, RuntimeError) as exc:
                raise ProjectionError(f"t-SNE 投影失败: {exc}") from exc

        # UMAP：可选依赖
        if method == ProjectionMethod.UMAP:
            try:
                import umap  # type: ignore[import]
            except ImportError as exc:
                raise ProjectionError(
                    "UMAP 需要 umap-learn，请安装: pip install umap-learn"
                ) from exc

            with self._reducer_lock:
                cached = self._reducer_cache.get(cache_key)
                if cached is not None:
                    _, reducer = cached
                else:
                    n_components = min(dim, n_features, n_samples - 1)
                    if n_components < dim:
                        raise ProjectionError(
                            f"UMAP 分量数 {n_components} 小于目标维度 {dim}"
                        )
                    reducer = umap.UMAP(
                        n_components=n_components,
                        random_state=42,
                    )
                    reducer.fit(data)
                    self._reducer_cache[cache_key] = (method, reducer)
            try:
                return reducer.transform(data)[:, :dim]
            except (ValueError, RuntimeError) as exc:
                raise ProjectionError(f"UMAP 投影失败: {exc}") from exc

        raise ProjectionError(f"未知降维方法: {method}")

    # ── payload 持久化 ────────────────────────────────────────────────

    def _persist_payload(
        self, payload: dict[str, Any], explanation_id: str
    ) -> tuple[str, int]:
        """将 payload 写入 JSON 文件.

        Returns
        -------
        tuple[str, int]
            (payload_path, payload_size_bytes)
        """
        payload_path = os.path.join(self._payloads_root, f"{explanation_id}.json")
        try:
            with open(payload_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
        except (OSError, IOError, TypeError, ValueError) as exc:
            raise ProjectionError(
                f"payload 持久化失败: {exc}"
            ) from exc
        size = os.path.getsize(payload_path)
        return payload_path, size

    def _load_payload(self, payload_path: str) -> dict[str, Any]:
        """读取 payload JSON 文件."""
        try:
            with open(payload_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, IOError, json.JSONDecodeError, TypeError) as exc:
            raise ProjectionError(f"payload 读取失败: {exc}") from exc

    def _delete_payload(self, payload_path: str) -> None:
        """删除 payload 文件（不存在时静默忽略）."""
        try:
            if os.path.exists(payload_path):
                os.remove(payload_path)
        except (OSError, IOError) as exc:
            logger.warning(
                "删除 payload 文件失败 path=%s: %s",
                payload_path,
                exc,
            )

    # ── 数据库记录辅助 ────────────────────────────────────────────────

    async def _create_record(
        self,
        *,
        explanation_type: str,
        model_uri: str,
        source_snapshot_id: Optional[str],
        input_signature: str,
        payload_path: str,
        payload_size_bytes: int,
        metadata: dict[str, Any],
        created_by: Optional[str],
    ) -> ExplanationRecord:
        """写入解释记录到数据库."""
        record_orm = ExplanationRecordORM(
            id=_gen_explanation_id(),
            explanation_type=explanation_type,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_signature=input_signature,
            payload_path=payload_path,
            payload_size_bytes=payload_size_bytes,
            metadata_json=json.dumps(metadata, ensure_ascii=False, default=str),
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        session = await self._get_session()
        try:
            async with session.begin():
                session.add(record_orm)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise ProjectionError(f"写入解释记录失败: {exc}") from exc
        finally:
            await session.close()

        return ExplanationRecord(
            id=record_orm.id,
            explanation_type=record_orm.explanation_type,
            model_uri=record_orm.model_uri,
            source_snapshot_id=record_orm.source_snapshot_id,
            input_signature=record_orm.input_signature,
            payload_path=record_orm.payload_path,
            payload_size_bytes=record_orm.payload_size_bytes,
            metadata_json=metadata,
            created_by=record_orm.created_by,
            created_at=record_orm.created_at,
            expires_at=record_orm.expires_at,
        )

    async def _find_record_orm(
        self, explanation_id: str
    ) -> ExplanationRecordORM:
        """查询解释记录 ORM（不存在抛 ExplanationLookupError）."""
        session = await self._get_session()
        try:
            async with session.begin():
                stmt = select(ExplanationRecordORM).where(
                    ExplanationRecordORM.id == explanation_id
                )
                result = await session.execute(stmt)
                record_orm = result.scalar_one_or_none()
            if record_orm is None:
                raise ExplanationLookupError(explanation_id)
            return record_orm
        finally:
            await session.close()

    # ==================================================================
    # IExplainabilityService 实现
    # ==================================================================

    async def generate_hidden_state_explanation(
        self,
        model_uri: str,
        *,
        source_snapshot_id: Optional[str] = None,
        projection_method: str = ProjectionMethod.PCA,
        projection_dim: int = 2,
        max_frames: int = 1000,
        created_by: Optional[str] = None,
    ) -> ExplanationRecord:
        """生成隐状态投影解释."""
        if not ProjectionMethod.is_valid(projection_method):
            raise ExplanationValidationError(
                f"projection_method 不合法: {projection_method}"
            )
        if projection_dim not in (2, 3):
            raise ExplanationValidationError(
                f"projection_dim 必须为 2 或 3，当前: {projection_dim}"
            )
        if max_frames < 1:
            raise ExplanationValidationError(
                f"max_frames 必须 >= 1，当前: {max_frames}"
            )

        predictor = self._get_predictor(model_uri)

        # 调用 predict_with_intermediates 捕获隐状态
        # 使用零输入触发模型前向（v1：隐状态来自模型初始状态 + 前向）
        # 真实场景应从 source_snapshot_id 加载历史输入，v1 简化为零向量探测
        try:
            # 构造探测输入：从模型 config 推断 input_dim
            model_config = getattr(predictor.model, "config", None)
            input_dim = getattr(model_config, "input_size", 8) if model_config else 8
            probe_input = np.zeros((1, input_dim), dtype=np.float32)
            result = predictor.predict_with_intermediates(
                probe_input, capture_hidden=True, capture_gates=False
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            raise ProjectionError(
                f"predict_with_intermediates 调用失败: {exc}"
            ) from exc

        intermediates = result.model_info.get("intermediates", {}) or {}
        hidden_states_raw = intermediates.get("hidden_states", [])
        if not hidden_states_raw:
            raise ProjectionError(
                "模型未捕获到隐状态，无法生成隐状态投影解释"
                f"（capture_mode={intermediates.get('capture_mode', 'disabled')}）"
            )

        hidden_array = np.asarray(hidden_states_raw, dtype=np.float32)
        # 下采样到 max_frames
        if hidden_array.shape[0] > max_frames:
            indices = np.linspace(
                0, hidden_array.shape[0] - 1, max_frames, dtype=int
            )
            hidden_array = hidden_array[indices]

        # 降维投影
        projections = self._project(
            projection_method, hidden_array, projection_dim, model_uri
        )

        # 计算能量（L2 范数平方均值）
        energies = (
            np.mean(hidden_array ** 2, axis=1).astype(float).tolist()
            if hidden_array.size > 0
            else []
        )

        # v1：所有帧标记为关键帧（不从 StreamingPredictor 获取关键帧标记）
        keyframe_flags = [True] * len(hidden_array)
        frame_ids = list(range(len(hidden_array)))

        explanation = HiddenStateExplanation(
            frame_ids=frame_ids,
            projections=projections.astype(float).tolist(),
            energies=energies,
            keyframe_flags=keyframe_flags,
            projection_method=projection_method,
            projection_dim=projection_dim,
            hidden_dim=int(hidden_array.shape[1]),
            sample_count=len(hidden_array),
            model_uri=model_uri,
        )

        # 计算 input_signature（用于去重）
        request = ExplanationRequest(
            explanation_type=ExplanationType.HIDDEN_STATE,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            options={
                "projection_method": projection_method,
                "projection_dim": projection_dim,
                "max_frames": max_frames,
            },
            created_by=created_by,
        )

        # 持久化 payload
        record_id = _gen_explanation_id()
        payload_path, payload_size = self._persist_payload(
            explanation.to_payload(), record_id
        )

        return await self._create_record(
            explanation_type=ExplanationType.HIDDEN_STATE,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_signature=request.input_signature(),
            payload_path=payload_path,
            payload_size_bytes=payload_size,
            metadata={
                "projection_method": projection_method,
                "projection_dim": projection_dim,
                "sample_count": len(hidden_array),
                "hidden_dim": int(hidden_array.shape[1]),
                "capture_mode": intermediates.get("capture_mode", "disabled"),
            },
            created_by=created_by,
        )

    async def generate_gate_dynamics_explanation(
        self,
        model_uri: str,
        *,
        source_snapshot_id: Optional[str] = None,
        anomaly_sigma: float = 2.0,
        created_by: Optional[str] = None,
    ) -> ExplanationRecord:
        """生成门控动力学解释."""
        if anomaly_sigma <= 0:
            raise ExplanationValidationError(
                f"anomaly_sigma 必须为正数，当前: {anomaly_sigma}"
            )

        predictor = self._get_predictor(model_uri)

        try:
            model_config = getattr(predictor.model, "config", None)
            input_dim = getattr(model_config, "input_size", 8) if model_config else 8
            probe_input = np.zeros((1, input_dim), dtype=np.float32)
            result = predictor.predict_with_intermediates(
                probe_input, capture_hidden=True, capture_gates=True
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            raise ProjectionError(
                f"predict_with_intermediates 调用失败: {exc}"
            ) from exc

        intermediates = result.model_info.get("intermediates", {}) or {}
        gate_values_raw = intermediates.get("gate_values", [])
        time_constants_raw = intermediates.get("time_constants", [])

        if not gate_values_raw:
            raise ProjectionError(
                "模型未捕获到门控值，无法生成门控动力学解释"
                f"（capture_mode={intermediates.get('capture_mode', 'disabled')}）"
            )

        gate_array = np.asarray(gate_values_raw, dtype=np.float32)
        # 每个特征的全局平均门控值
        mean_gate_per_feature = (
            np.mean(gate_array, axis=0).astype(float).tolist()
            if gate_array.size > 0
            else []
        )

        # 异常帧检测：门控值超过 mean ± sigma*std
        anomaly_frames: list[int] = []
        if gate_array.ndim == 2 and gate_array.shape[0] > 1:
            mean = np.mean(gate_array, axis=0)
            std = np.std(gate_array, axis=0)
            for frame_idx in range(gate_array.shape[0]):
                deviations = np.abs(gate_array[frame_idx] - mean)
                if np.any(deviations > anomaly_sigma * (std + 1e-8)):
                    anomaly_frames.append(frame_idx)

        frame_ids = list(range(len(gate_values_raw)))
        explanation = GateDynamicsExplanation(
            frame_ids=frame_ids,
            gate_values=gate_values_raw,
            time_constants=time_constants_raw,
            mean_gate_per_feature=mean_gate_per_feature,
            anomaly_frames=anomaly_frames,
            model_uri=model_uri,
        )

        request = ExplanationRequest(
            explanation_type=ExplanationType.GATE_DYNAMICS,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            options={"anomaly_sigma": anomaly_sigma},
            created_by=created_by,
        )

        record_id = _gen_explanation_id()
        payload_path, payload_size = self._persist_payload(
            explanation.to_payload(), record_id
        )

        return await self._create_record(
            explanation_type=ExplanationType.GATE_DYNAMICS,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_signature=request.input_signature(),
            payload_path=payload_path,
            payload_size_bytes=payload_size,
            metadata={
                "anomaly_sigma": anomaly_sigma,
                "frame_count": len(gate_values_raw),
                "anomaly_frame_count": len(anomaly_frames),
                "capture_mode": intermediates.get("capture_mode", "disabled"),
            },
            created_by=created_by,
        )

    async def generate_counterfactual_explanation(
        self,
        model_uri: str,
        *,
        base_input: dict[str, float],
        perturbed_feature: str,
        perturbation_range: Optional[list[float]] = None,
        perturbation_step: float = 0.05,
        source_snapshot_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> ExplanationRecord:
        """生成反事实解释."""
        if not base_input:
            raise ExplanationValidationError("base_input 不能为空")
        if not perturbed_feature:
            raise ExplanationValidationError("perturbed_feature 不能为空")
        if perturbed_feature not in base_input:
            raise ExplanationValidationError(
                f"perturbed_feature '{perturbed_feature}' 不在 base_input 中"
            )
        if perturbation_step <= 0:
            raise ExplanationValidationError(
                f"perturbation_step 必须为正数，当前: {perturbation_step}"
            )

        # 生成扰动序列（相对基准值的比例）
        if perturbation_range is None:
            # 默认 ±20%，步长 perturbation_step
            steps = int(0.2 / perturbation_step)
            perturbation_range = [
                round(-0.2 + i * perturbation_step, 4)
                for i in range(-steps, steps + 1)
            ]
        if not perturbation_range:
            raise ExplanationValidationError("perturbation_range 不能为空")

        predictor = self._get_predictor(model_uri)
        base_value = float(base_input[perturbed_feature])

        # 逐点扰动推理
        outputs: list[float] = []
        for perturbation in perturbation_range:
            perturbed_input = dict(base_input)
            perturbed_input[perturbed_feature] = base_value * (1.0 + perturbation)
            try:
                # 构造输入向量（按 base_input 的值顺序）
                input_vector = np.array(
                    list(perturbed_input.values()), dtype=np.float32
                ).reshape(1, -1)
                result = predictor.predict(input_vector)
                output_value = result if not isinstance(result, dict) else (
                    result.get("value", 0.0)
                )
                # 标量化
                if hasattr(output_value, "item"):
                    output_value = float(output_value.item())
                elif hasattr(output_value, "__iter__"):
                    output_value = float(np.mean(output_value))
                else:
                    output_value = float(output_value)
                outputs.append(output_value)
            except (ValueError, TypeError, RuntimeError) as exc:
                logger.warning(
                    "反事实推理失败 perturbation=%.4f: %s",
                    perturbation,
                    exc,
                )
                outputs.append(0.0)

        # 计算敏感度（一阶导数均值）
        outputs_array = np.asarray(outputs, dtype=np.float32)
        if len(outputs) >= 2:
            diffs = np.diff(outputs_array) / (
                np.diff(perturbation_range) + 1e-8
            )
            sensitivity = float(np.mean(np.abs(diffs)))
        else:
            sensitivity = 0.0

        # 识别临界点（差分突变）
        critical_points: list[dict[str, Any]] = []
        if len(outputs) >= 3:
            deltas = np.abs(np.diff(outputs_array))
            mean_delta = float(np.mean(deltas)) if deltas.size > 0 else 0.0
            threshold = mean_delta * 2.0 if mean_delta > 0 else 0.0
            for i in range(1, len(outputs) - 1):
                delta = float(abs(outputs[i] - outputs[i - 1]))
                if delta > threshold and threshold > 0:
                    critical_points.append(
                        {
                            "perturbation": perturbation_range[i],
                            "output": outputs[i],
                            "delta": delta,
                        }
                        )

        explanation = CounterfactualExplanation(
            base_input=dict(base_input),
            perturbed_feature=perturbed_feature,
            perturbation_range=list(perturbation_range),
            outputs=outputs,
            sensitivity=sensitivity,
            critical_points=critical_points,
            model_uri=model_uri,
        )

        request = ExplanationRequest(
            explanation_type=ExplanationType.COUNTERFACTUAL,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_data={
                "base_input": base_input,
                "perturbed_feature": perturbed_feature,
            },
            options={
                "perturbation_step": perturbation_step,
                "perturbation_range": perturbation_range,
            },
            created_by=created_by,
        )

        record_id = _gen_explanation_id()
        payload_path, payload_size = self._persist_payload(
            explanation.to_payload(), record_id
        )

        return await self._create_record(
            explanation_type=ExplanationType.COUNTERFACTUAL,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_signature=request.input_signature(),
            payload_path=payload_path,
            payload_size_bytes=payload_size,
            metadata={
                "perturbed_feature": perturbed_feature,
                "sensitivity": sensitivity,
                "critical_point_count": len(critical_points),
                "perturbation_point_count": len(perturbation_range),
            },
            created_by=created_by,
        )

    async def generate_confidence_explanation(
        self,
        model_uri: str,
        *,
        input_data: dict[str, Any],
        sample_count: int = 30,
        source_snapshot_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> ExplanationRecord:
        """生成置信度分布解释（MC dropout 采样）."""
        if not input_data:
            raise ExplanationValidationError("input_data 不能为空")
        if sample_count <= 0:
            raise ExplanationValidationError(
                f"sample_count 必须为正数，当前: {sample_count}"
            )
        if sample_count > 200:
            raise ExplanationValidationError(
                f"sample_count 上限 200，当前: {sample_count}"
            )

        predictor = self._get_predictor(model_uri)

        # 构造输入向量
        try:
            input_vector = np.array(
                list(input_data.values()), dtype=np.float32
            ).reshape(1, -1)
        except (ValueError, TypeError) as exc:
            raise ExplanationValidationError(
                f"input_data 无法转换为数值向量: {exc}"
            ) from exc

        # 调用 MC dropout 采样
        try:
            mc_result = predictor.predict_mc_dropout(
                input_vector, n_samples=sample_count
            )
        except (ValueError, TypeError, RuntimeError) as exc:
            raise SamplingError(f"MC dropout 采样失败: {exc}") from exc

        mc_info = mc_result.model_info or {}
        mc_mean = float(mc_info.get("mc_mean", 0.0))
        mc_std = float(mc_info.get("mc_std", 0.0))

        # v1：单点采样的均值/方差，分位数与直方图为简化估计
        # 真实分布需要 predict_mc_dropout 返回所有样本，v1 保守估计
        percentiles = {
            "p5": mc_mean - 1.645 * mc_std if mc_std > 0 else mc_mean,
            "p25": mc_mean - 0.674 * mc_std if mc_std > 0 else mc_mean,
            "p50": mc_mean,
            "p75": mc_mean + 0.674 * mc_std if mc_std > 0 else mc_mean,
            "p95": mc_mean + 1.645 * mc_std if mc_std > 0 else mc_mean,
        }

        # 直方图（基于正态假设生成 20 个 bin 的计数）
        if mc_std > 0:
            bins = np.linspace(
                mc_mean - 3 * mc_std, mc_mean + 3 * mc_std, 21
            ).tolist()
            # 简化：使用正态分布 CDF 差分估算计数
            from math import erf, sqrt

            counts = []
            for i in range(len(bins) - 1):
                cdf_low = 0.5 * (1 + erf((bins[i] - mc_mean) / (mc_std * sqrt(2))))
                cdf_high = 0.5 * (
                    1 + erf((bins[i + 1] - mc_mean) / (mc_std * sqrt(2)))
                )
                counts.append(int((cdf_high - cdf_low) * sample_count))
            histogram = {"bins": bins, "counts": counts}
        else:
            histogram = {
                "bins": [mc_mean, mc_mean],
                "counts": [sample_count],
            }

        # 认知不确定性 = std（可由数据降低）
        epistemic = mc_std
        # 偶然不确定性：v1 简化为 0（需要多次输入扰动估计，留待 v2）
        aleatoric = 0.0
        # 异常分数
        anomaly_score = mc_std / (abs(mc_mean) + 1e-8)

        explanation = ConfidenceExplanation(
            sample_count=sample_count,
            mean=mc_mean,
            std=mc_std,
            percentiles=percentiles,
            histogram=histogram,
            epistemic=epistemic,
            aleatoric=aleatoric,
            anomaly_score=anomaly_score,
            model_uri=model_uri,
        )

        request = ExplanationRequest(
            explanation_type=ExplanationType.CONFIDENCE,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_data=input_data,
            options={"sample_count": sample_count},
            created_by=created_by,
        )

        record_id = _gen_explanation_id()
        payload_path, payload_size = self._persist_payload(
            explanation.to_payload(), record_id
        )

        return await self._create_record(
            explanation_type=ExplanationType.CONFIDENCE,
            model_uri=model_uri,
            source_snapshot_id=source_snapshot_id,
            input_signature=request.input_signature(),
            payload_path=payload_path,
            payload_size_bytes=payload_size,
            metadata={
                "sample_count": sample_count,
                "mean": mc_mean,
                "std": mc_std,
                "anomaly_score": anomaly_score,
            },
            created_by=created_by,
        )

    async def get_explanation(
        self, explanation_id: str, *, include_payload: bool = False
    ) -> dict[str, Any]:
        """查询解释结果."""
        record_orm = await self._find_record_orm(explanation_id)
        result = record_orm.to_dict()
        if include_payload:
            try:
                result["payload"] = self._load_payload(record_orm.payload_path)
            except ProjectionError as exc:
                logger.warning(
                    "读取 payload 失败 explanation_id=%s: %s",
                    explanation_id,
                    exc,
                )
                result["payload"] = None
                result["payload_error"] = str(exc)
        return result

    async def list_explanations(
        self,
        *,
        explanation_type: Optional[str] = None,
        model_uri: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ExplanationRecord], int]:
        """列出历史解释记录."""
        if limit < 1 or limit > 500:
            raise ExplanationValidationError(
                f"limit 必须在 [1, 500]，当前: {limit}"
            )
        if offset < 0:
            raise ExplanationValidationError(
                f"offset 必须 >= 0，当前: {offset}"
            )

        session = await self._get_session()
        try:
            async with session.begin():
                # 构造查询条件
                conditions = []
                if explanation_type:
                    if not ExplanationType.is_valid(explanation_type):
                        raise ExplanationValidationError(
                            f"explanation_type 不合法: {explanation_type}"
                        )
                    conditions.append(
                        ExplanationRecordORM.explanation_type == explanation_type
                    )
                if model_uri:
                    conditions.append(
                        ExplanationRecordORM.model_uri == model_uri
                    )

                # 总数查询
                count_stmt = select(func.count()).select_from(
                    ExplanationRecordORM
                )
                for cond in conditions:
                    count_stmt = count_stmt.where(cond)
                total = (await session.execute(count_stmt)).scalar_one()

                # 分页查询
                list_stmt = select(ExplanationRecordORM).order_by(
                    desc(ExplanationRecordORM.created_at)
                ).offset(offset).limit(limit)
                for cond in conditions:
                    list_stmt = list_stmt.where(cond)
                records = (
                    (await session.execute(list_stmt))
                    .scalars()
                    .all()
                )
            records_list = [
                ExplanationRecord(
                    id=r.id,
                    explanation_type=r.explanation_type,
                    model_uri=r.model_uri,
                    source_snapshot_id=r.source_snapshot_id,
                    input_signature=r.input_signature,
                    payload_path=r.payload_path,
                    payload_size_bytes=r.payload_size_bytes,
                    metadata_json=json.loads(r.metadata_json)
                    if r.metadata_json
                    else {},
                    created_by=r.created_by,
                    created_at=r.created_at,
                    expires_at=r.expires_at,
                )
                for r in records
            ]
            return records_list, int(total)
        finally:
            await session.close()

    async def delete_explanation(self, explanation_id: str) -> bool:
        """删除解释记录（同时删除 payload 文件）."""
        record_orm = await self._find_record_orm(explanation_id)
        payload_path = record_orm.payload_path

        session = await self._get_session()
        try:
            async with session.begin():
                await session.delete(record_orm)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise ProjectionError(f"删除解释记录失败: {exc}") from exc
        finally:
            await session.close()

        # 删除 payload 文件
        self._delete_payload(payload_path)
        return True

    async def compare_explanations(
        self,
        base_explanation_id: str,
        compared_explanation_id: str,
        *,
        comparison_type: str = ComparisonType.SAME_MODEL_DIFF_INPUT,
        created_by: Optional[str] = None,
    ) -> ExplanationComparison:
        """对比两个解释."""
        if not ComparisonType.is_valid(comparison_type):
            raise ExplanationValidationError(
                f"comparison_type 不合法: {comparison_type}"
            )
        if base_explanation_id == compared_explanation_id:
            raise ExplanationValidationError(
                "base 与 compared 不能为相同解释"
            )

        # 查询两条记录
        base_orm = await self._find_record_orm(base_explanation_id)
        compared_orm = await self._find_record_orm(compared_explanation_id)

        # 类型一致性校验
        if base_orm.explanation_type != compared_orm.explanation_type:
            from app.contracts.explainability import ComparisonMismatchError

            raise ComparisonMismatchError(
                f"解释类型不一致: base={base_orm.explanation_type} "
                f"compared={compared_orm.explanation_type}"
            )

        # 加载 payload
        base_payload = self._load_payload(base_orm.payload_path)
        compared_payload = self._load_payload(compared_orm.payload_path)

        # 计算差异 payload
        diff_payload = self._compute_diff(
            base_payload, compared_payload, base_orm.explanation_type
        )

        comparison_id = _gen_comparison_id()
        diff_path = os.path.join(
            self._payloads_root, f"{comparison_id}_diff.json"
        )
        try:
            with open(diff_path, "w", encoding="utf-8") as f:
                json.dump(diff_payload, f, ensure_ascii=False, default=str)
        except (OSError, IOError, TypeError, ValueError) as exc:
            raise ProjectionError(
                f"差异 payload 持久化失败: {exc}"
            ) from exc

        # 写入数据库
        comparison_orm = ExplanationComparisonORM(
            id=comparison_id,
            base_explanation_id=base_explanation_id,
            compared_explanation_id=compared_explanation_id,
            comparison_type=comparison_type,
            diff_payload_path=diff_path,
            created_by=created_by,
            created_at=datetime.utcnow(),
        )
        session = await self._get_session()
        try:
            async with session.begin():
                session.add(comparison_orm)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            raise ProjectionError(f"写入对比记录失败: {exc}") from exc
        finally:
            await session.close()

        return ExplanationComparison(
            id=comparison_orm.id,
            base_explanation_id=comparison_orm.base_explanation_id,
            compared_explanation_id=comparison_orm.compared_explanation_id,
            comparison_type=comparison_orm.comparison_type,
            diff_payload_path=comparison_orm.diff_payload_path,
            created_by=comparison_orm.created_by,
            created_at=comparison_orm.created_at,
        )

    # ── 差异计算 ──────────────────────────────────────────────────────

    def _compute_diff(
        self,
        base: dict[str, Any],
        compared: dict[str, Any],
        explanation_type: str,
    ) -> dict[str, Any]:
        """计算两个解释 payload 的差异.

        根据 explanation_type 选择差异计算策略：
        - hidden_state：投影坐标的 L2 距离 + 能量差
        - gate_dynamics：门控值的逐帧差分 + 异常帧差异
        - counterfactual：输出曲线的逐点差分 + 敏感度差
        - confidence：均值/标准差/异常分数差
        """
        diff: dict[str, Any] = {
            "explanation_type": explanation_type,
            "base_summary": {},
            "compared_summary": {},
            "differences": {},
        }

        if explanation_type == ExplanationType.HIDDEN_STATE:
            base_proj = np.asarray(base.get("projections", []), dtype=float)
            comp_proj = np.asarray(compared.get("projections", []), dtype=float)
            base_energy = np.asarray(base.get("energies", []), dtype=float)
            comp_energy = np.asarray(compared.get("energies", []), dtype=float)

            diff["base_summary"] = {
                "sample_count": base.get("sample_count", 0),
                "mean_energy": float(np.mean(base_energy)) if base_energy.size else 0.0,
            }
            diff["compared_summary"] = {
                "sample_count": compared.get("sample_count", 0),
                "mean_energy": float(np.mean(comp_energy)) if comp_energy.size else 0.0,
            }
            # 对齐长度后计算距离
            min_len = min(len(base_proj), len(comp_proj))
            if min_len > 0:
                distances = np.linalg.norm(
                    base_proj[:min_len] - comp_proj[:min_len], axis=1
                )
                diff["differences"] = {
                    "mean_distance": float(np.mean(distances)),
                    "max_distance": float(np.max(distances)),
                    "energy_diff": float(
                        np.mean(comp_energy[:min_len] - base_energy[:min_len])
                    ),
                }

        elif explanation_type == ExplanationType.GATE_DYNAMICS:
            base_gates = np.asarray(base.get("gate_values", []), dtype=float)
            comp_gates = np.asarray(compared.get("gate_values", []), dtype=float)
            diff["base_summary"] = {
                "frame_count": len(base.get("frame_ids", [])),
                "anomaly_frame_count": len(base.get("anomaly_frames", [])),
            }
            diff["compared_summary"] = {
                "frame_count": len(compared.get("frame_ids", [])),
                "anomaly_frame_count": len(compared.get("anomaly_frames", [])),
            }
            min_len = min(len(base_gates), len(comp_gates))
            if min_len > 0:
                diffs = np.abs(base_gates[:min_len] - comp_gates[:min_len])
                diff["differences"] = {
                    "mean_gate_diff": float(np.mean(diffs)),
                    "max_gate_diff": float(np.max(diffs)),
                }

        elif explanation_type == ExplanationType.COUNTERFACTUAL:
            base_outputs = np.asarray(base.get("outputs", []), dtype=float)
            comp_outputs = np.asarray(compared.get("outputs", []), dtype=float)
            diff["base_summary"] = {
                "sensitivity": base.get("sensitivity", 0.0),
                "critical_point_count": len(base.get("critical_points", [])),
            }
            diff["compared_summary"] = {
                "sensitivity": compared.get("sensitivity", 0.0),
                "critical_point_count": len(compared.get("critical_points", [])),
            }
            min_len = min(len(base_outputs), len(comp_outputs))
            if min_len > 0:
                output_diffs = base_outputs[:min_len] - comp_outputs[:min_len]
                diff["differences"] = {
                    "mean_output_diff": float(np.mean(output_diffs)),
                    "max_output_diff": float(np.max(np.abs(output_diffs))),
                    "sensitivity_diff": float(
                        base.get("sensitivity", 0.0)
                        - compared.get("sensitivity", 0.0)
                    ),
                }

        elif explanation_type == ExplanationType.CONFIDENCE:
            diff["base_summary"] = {
                "mean": base.get("mean", 0.0),
                "std": base.get("std", 0.0),
                "anomaly_score": base.get("anomaly_score", 0.0),
            }
            diff["compared_summary"] = {
                "mean": compared.get("mean", 0.0),
                "std": compared.get("std", 0.0),
                "anomaly_score": compared.get("anomaly_score", 0.0),
            }
            diff["differences"] = {
                "mean_diff": float(
                    base.get("mean", 0.0) - compared.get("mean", 0.0)
                ),
                "std_diff": float(
                    base.get("std", 0.0) - compared.get("std", 0.0)
                ),
                "anomaly_score_diff": float(
                    base.get("anomaly_score", 0.0)
                    - compared.get("anomaly_score", 0.0)
                ),
            }

        return diff


__all__ = [
    "ExplainabilityService",
    "get_explainability_service",
    "reset_explainability_service",
    # 异常类（re-export 供路由层统一导入，与 project_package_service 风格一致）
    "ExplainabilityError",
    "ExplanationLookupError",
    "ExplanationValidationError",
    "ProjectionError",
    "SamplingError",
    "ComparisonMismatchError",
]
