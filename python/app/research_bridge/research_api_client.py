"""研究模块的稳定 API 客户端：产品轨调用研究模块的唯一通道。

设计：
- research_api_client 走 subprocess 隔离，调用 research 目录下的脚本
- 这样产品代码不会 import research/，保证双轨隔离
- 返回值用 research/shared/contracts 中定义的稳定 schema
- 调用失败时返回 None，并记录到错误样本
"""
from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

from .data_collector import UsageDataCollector

logger = logging.getLogger(__name__)

# research 目录的根（绝对路径）
REPO_ROOT = Path(__file__).resolve().parents[3]
RESEARCH_ROOT = REPO_ROOT / "research"

# 子进程运行时的 Python 解释器
PYTHON_BIN = sys.executable

# 安全修复：模块名和函数名白名单正则，防止命令注入
# 仅允许字母/数字/下划线/点，且必须以字母或下划线开头
_SAFE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")


class ResearchApiError(Exception):
    """研究 API 调用错误。"""

    pass


class ResearchApiClient:
    """研究模块的稳定 API 客户端（单例）。"""

    _instance: Optional["ResearchApiClient"] = None

    def __init__(self, timeout_sec: float = 30.0):
        self._timeout = timeout_sec
        self._collector = UsageDataCollector.get_instance()

    @classmethod
    def get_instance(cls) -> "ResearchApiClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def call_feature_recognizer(
        self,
        input_data: dict,
        recognizer: str = "ijepa_3d_recognizer",
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        """调用研究模块的特征识别器。

        recognizer: "ijepa_3d_recognizer" | "rule_based_recognizer"
        返回值格式（稳定契约）：
            {
                "status": "ok" | "error",
                "features": [
                    {"type": "chamfer", "params": {...}},
                    ...
                ],
                "confidence": 0.0-1.0,
                "latency_ms": int
            }
        """
        return self._call_subprocess(
            module="research.multimodal_jepa.ijepa_3d.inference_bridge"
            if recognizer == "ijepa_3d_recognizer"
            else "research.shared.contracts.dummy_recognizer",
            func="recognize",
            payload=input_data,
            user_id=user_id,
        )

    def call_bayesian_lnn(
        self,
        input_data: dict,
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        """调用 Bayesian-LNN 不确定性量化。

        返回值格式：
            {
                "status": "ok",
                "mean": float,
                "std": float,
                "samples": [float, ...]
            }
        """
        return self._call_subprocess(
            module="research.lnn_research.bayesian_lnn",
            func="predict_with_uncertainty",
            payload=input_data,
            user_id=user_id,
        )

    def _call_subprocess(
        self,
        module: str,
        func: str,
        payload: dict,
        user_id: Optional[str] = None,
    ) -> Optional[dict]:
        """通过子进程调用研究模块。"""
        # 安全修复：校验 module 和 func 防止命令注入
        if not _SAFE_IDENT_RE.match(module):
            logger.error("Invalid module name rejected: %r", module)
            return None
        if not _SAFE_IDENT_RE.match(func):
            logger.error("Invalid function name rejected: %r", func)
            return None
        t0 = time.perf_counter()
        try:
            # 把 payload 序列化成 JSON 字符串作为参数
            payload_str = json.dumps(payload, ensure_ascii=False)
            cmd = [
                PYTHON_BIN,
                "-c",
                f"import sys, json; sys.path.insert(0, r'{REPO_ROOT}'); "
                f"from {module} import {func}; "
                f"print(json.dumps({func}(json.loads(sys.argv[1])), ensure_ascii=False, default=str))",
                payload_str,
            ]
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
            )
            if proc.returncode != 0:
                err_msg = proc.stderr.strip() or f"returncode={proc.returncode}"
                self._collector.record_error(
                    feature=module,
                    error_type="subprocess_failed",
                    error_message=err_msg,
                    context={"payload_keys": list(payload.keys())},
                    user_id=user_id,
                )
                return None
            # 解析最后一行 JSON
            last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
            result = json.loads(last_line)
            latency = int((time.perf_counter() - t0) * 1000)
            self._collector.record_recognition(
                feature=module,
                dxf_path=payload.get("file_path", ""),
                success=True,
                latency_ms=latency,
                user_id=user_id,
            )
            return result
        except subprocess.TimeoutExpired:
            self._collector.record_error(
                feature=module,
                error_type="timeout",
                error_message=f"timeout>{self._timeout}s",
                user_id=user_id,
            )
            return None
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError, TypeError) as e:
            self._collector.record_error(
                feature=module,
                error_type="call_failed",
                error_message=repr(e),
                user_id=user_id,
            )
            return None


__all__ = ["ResearchApiClient", "ResearchApiError"]
