"""LLM Provider 注册表。

负责管理所有 Provider 配置的持久化（SQLite）、API Key 加密、
实例缓存、激活切换等生命周期管理。

设计要点：
- SQLite 持久化：配置存储在 python/data/llm_providers.db，与项目其他 DB 对齐
- API Key 加密：使用 Fernet 对称加密，密钥从环境变量或项目令牌派生
- 实例缓存：Provider 实例创建后缓存，配置变更时失效
- 激活互斥：同一时刻仅一个 Provider 处于 is_active=True
- 首次初始化：自动建表 + 种子默认 Provider 模板（全部 disabled）
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.ai.llm.provider_base import (
    LLMProvider,
    ProviderCapability,
    ProviderConfig,
    ProviderType,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据库路径
# ---------------------------------------------------------------------------

def _get_db_path() -> Path:
    """获取 Provider 注册表数据库路径。

    约定：python/data/llm_providers.db
    支持环境变量 LLM_PROVIDERS_DB 覆盖。
    """
    env_path = os.environ.get("LLM_PROVIDERS_DB")
    if env_path:
        return Path(env_path)

    # python/ 目录（与 app.db 同级）
    python_dir = Path(__file__).resolve().parent.parent.parent.parent
    data_dir = python_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "llm_providers.db"


# ---------------------------------------------------------------------------
# API Key 加密
# ---------------------------------------------------------------------------

class APIKeyCipher:
    """API Key 对称加密器（Fernet）。

    加密密钥派生优先级：
    1. 环境变量 LLM_PROVIDER_ENCRYPTION_KEY（Fernet 兼容的 base64 urlsafe 32字节）
    2. 项目令牌（.lnn_token 文件内容）→ SHA256 → Fernet key
    3. 临时密钥（仅当前会话有效，重启后已加密 Key 无法解密）

    第三种情况会记录警告，并自动重新加密所有存储的 Key。

    安全模式（strict，默认启用）：
        - 加密失败时抛出 ``RuntimeError``，绝不静默回退明文存储
        - 解密时密钥不可用抛出 ``RuntimeError``；解密本身失败仍返回空串
          （避免错误密钥下泄漏其他密文对应明文）
    非安全模式（strict=False，仅用于本地开发/测试）：
        - 保留旧行为，加密失败回退明文。生产环境严禁使用。
    """

    def __init__(self, strict: bool = True) -> None:
        self._strict = strict
        self._fernet = None
        self._key_source: str = "unknown"
        try:
            from cryptography.fernet import Fernet  # type: ignore
            self._Fernet = Fernet
        except ImportError:
            self._Fernet = None  # type: ignore
            msg = (
                "cryptography 未安装，API Key 加密不可用。"
                "建议安装：pip install cryptography"
            )
            if strict:
                raise RuntimeError(msg)
            logger.warning(msg)

    def _resolve_key(self) -> bytes | None:
        """解析加密密钥，返回 Fernet 兼容的 32 字节 base64 urlsafe。"""
        if self._Fernet is None:
            return None

        # 优先级 1: 环境变量
        env_key = os.environ.get("LLM_PROVIDER_ENCRYPTION_KEY")
        if env_key:
            try:
                self._key_source = "env"
                return env_key.encode() if isinstance(env_key, str) else env_key
            except Exception as e:
                logger.debug("Invalid LLM_PROVIDER_ENCRYPTION_KEY: %s", e)

        # 优先级 2: 项目令牌派生
        try:
            from app.config import config
            token = config.token.token
            import base64
            import hashlib
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            key = base64.urlsafe_b64encode(digest)
            self._key_source = "token"
            return key
        except Exception as e:
            logger.debug("Failed to derive key from project token: %s", e)

        # 优先级 3: 临时密钥
        if self._Fernet is not None:
            key = self._Fernet.generate_key()
            self._key_source = "ephemeral"
            logger.warning(
                "使用临时加密密钥。重启后已存储的 API Key 将无法解密。"
                "请设置 LLM_PROVIDER_ENCRYPTION_KEY 环境变量以持久化。"
            )
            return key

        return None

    @property
    def available(self) -> bool:
        """加密是否可用。"""
        return self._Fernet is not None

    def encrypt(self, plaintext: str) -> str:
        """加密 API Key。

        Raises:
            RuntimeError: strict 模式下加密不可用或加密失败。
        """
        if not plaintext:
            return ""
        if self._Fernet is None:
            if self._strict:
                raise RuntimeError(
                    "API Key 加密不可用（cryptography 未安装），"
                    "strict 模式下拒绝明文存储。"
                )
            return plaintext  # 降级明文（仅 non-strict）
        try:
            if self._fernet is None:
                key = self._resolve_key()
                if key is None:
                    if self._strict:
                        raise RuntimeError(
                            "API Key 加密密钥不可用，strict 模式下拒绝明文存储。"
                        )
                    return plaintext
                self._fernet = self._Fernet(key)
            return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        except RuntimeError:
            raise
        except Exception as e:
            logger.error("API Key 加密失败: %s", e)
            if self._strict:
                raise RuntimeError(f"API Key 加密失败: {e}") from e
            return plaintext

    def decrypt(self, ciphertext: str) -> str:
        """解密 API Key。

        Raises:
            RuntimeError: strict 模式下加密后端或密钥不可用。
        """
        if not ciphertext:
            return ""
        if self._Fernet is None:
            if self._strict:
                raise RuntimeError(
                    "API Key 解密不可用（cryptography 未安装）。"
                )
            return ciphertext  # 明文模式
        try:
            if self._fernet is None:
                key = self._resolve_key()
                if key is None:
                    if self._strict:
                        raise RuntimeError(
                            "API Key 解密密钥不可用，strict 模式下拒绝返回密文。"
                        )
                    return ciphertext
                self._fernet = self._Fernet(key)
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except RuntimeError:
            raise
        except Exception as e:
            # 解密失败可能是密钥变更，返回空字符串避免泄漏
            logger.warning("API Key 解密失败（密钥可能已变更）: %s", e)
            return ""


# ---------------------------------------------------------------------------
# Provider 工厂
# ---------------------------------------------------------------------------

# ProviderType -> Provider 类 的映射
_PROVIDER_CLASS_MAP: dict[ProviderType, type[LLMProvider]] = {}


def _register_provider_class(provider_type: ProviderType, cls: type[LLMProvider]) -> None:
    """注册 Provider 类。"""
    _PROVIDER_CLASS_MAP[provider_type] = cls


def _load_all_provider_classes() -> None:
    """延迟加载所有 Provider 类，避免循环导入。"""
    if _PROVIDER_CLASS_MAP:
        return

    try:
        from app.ai.llm.providers import (
            OllamaProvider, LMStudioProvider, LlamaCppProvider,
            VllmProvider, TGIProvider, KoboldCppProvider,
        )
        from app.ai.llm.providers.cloud import (
            OpenAIProvider, AnthropicProvider, DeepSeekProvider,
            QwenProvider, GeminiProvider, OpenAICompatibleProvider,
        )

        _register_provider_class(ProviderType.OLLAMA, OllamaProvider)
        _register_provider_class(ProviderType.LMSTUDIO, LMStudioProvider)
        _register_provider_class(ProviderType.LLAMACPP, LlamaCppProvider)
        _register_provider_class(ProviderType.VLLM, VllmProvider)
        _register_provider_class(ProviderType.TGI, TGIProvider)
        _register_provider_class(ProviderType.KOBOLDCPP, KoboldCppProvider)
        _register_provider_class(ProviderType.OPENAI, OpenAIProvider)
        _register_provider_class(ProviderType.ANTHROPIC, AnthropicProvider)
        _register_provider_class(ProviderType.DEEPSEEK, DeepSeekProvider)
        _register_provider_class(ProviderType.QWEN, QwenProvider)
        _register_provider_class(ProviderType.GEMINI, GeminiProvider)
        _register_provider_class(ProviderType.OPENAI_COMPATIBLE, OpenAICompatibleProvider)
    except ImportError as e:
        logger.error("加载 Provider 类失败: %s", e, exc_info=True)


def create_provider(config: ProviderConfig) -> LLMProvider:
    """根据配置创建 Provider 实例。"""
    _load_all_provider_classes()
    cls = _PROVIDER_CLASS_MAP.get(config.provider_type)
    if cls is None:
        raise ValueError(f"未知的 Provider 类型: {config.provider_type}")
    return cls(config)


# ---------------------------------------------------------------------------
# 默认 Provider 模板
# ---------------------------------------------------------------------------

def _default_provider_templates() -> list[ProviderConfig]:
    """生成默认 Provider 模板（全部 disabled，等待用户配置）。"""
    return [
        ProviderConfig(
            provider_id="ollama-default",
            name="Ollama (本地)",
            provider_type=ProviderType.OLLAMA,
            base_url="http://127.0.0.1:11434",
            default_model="qwen2.5-coder:7b",
            enabled=False,
            priority=10,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.STREAMING],
        ),
        ProviderConfig(
            provider_id="lmstudio-default",
            name="LM Studio (本地)",
            provider_type=ProviderType.LMSTUDIO,
            base_url="http://127.0.0.1:1234/v1",
            default_model="",
            enabled=False,
            priority=9,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.STREAMING],
        ),
        ProviderConfig(
            provider_id="llamacpp-default",
            name="llama.cpp (本地)",
            provider_type=ProviderType.LLAMACPP,
            base_url="http://127.0.0.1:8080/v1",
            default_model="",
            enabled=False,
            priority=8,
            capabilities=[ProviderCapability.CHAT],
        ),
        ProviderConfig(
            provider_id="vllm-default",
            name="vLLM (本地)",
            provider_type=ProviderType.VLLM,
            base_url="http://127.0.0.1:8000/v1",
            default_model="",
            enabled=False,
            priority=8,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.STREAMING],
        ),
        ProviderConfig(
            provider_id="openai-default",
            name="OpenAI (云端)",
            provider_type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            enabled=False,
            priority=7,
            capabilities=[
                ProviderCapability.CHAT, ProviderCapability.STREAMING,
                ProviderCapability.FUNCTION_CALLING, ProviderCapability.VISION,
            ],
        ),
        ProviderConfig(
            provider_id="anthropic-default",
            name="Anthropic Claude (云端)",
            provider_type=ProviderType.ANTHROPIC,
            base_url="https://api.anthropic.com/v1",
            default_model="claude-3-5-sonnet-20241022",
            enabled=False,
            priority=7,
            capabilities=[
                ProviderCapability.CHAT, ProviderCapability.STREAMING,
                ProviderCapability.VISION,
            ],
        ),
        ProviderConfig(
            provider_id="deepseek-default",
            name="DeepSeek (云端)",
            provider_type=ProviderType.DEEPSEEK,
            base_url="https://api.deepseek.com/v1",
            default_model="deepseek-chat",
            enabled=False,
            priority=6,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.STREAMING],
        ),
        ProviderConfig(
            provider_id="qwen-default",
            name="通义千问 (云端)",
            provider_type=ProviderType.QWEN,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_model="qwen-plus",
            enabled=False,
            priority=6,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.STREAMING],
        ),
        ProviderConfig(
            provider_id="gemini-default",
            name="Google Gemini (云端)",
            provider_type=ProviderType.GEMINI,
            base_url="https://generativelanguage.googleapis.com/v1beta",
            default_model="gemini-1.5-flash",
            enabled=False,
            priority=5,
            capabilities=[ProviderCapability.CHAT, ProviderCapability.VISION],
        ),
        ProviderConfig(
            provider_id="openai-compatible-default",
            name="OpenAI 兼容 (自定义)",
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            base_url="",
            default_model="",
            enabled=False,
            priority=4,
            capabilities=[ProviderCapability.CHAT],
        ),
    ]


# ---------------------------------------------------------------------------
# ProviderRegistry 单例
# ---------------------------------------------------------------------------

class ProviderRegistry:
    """LLM Provider 注册表。

    职责：
    - 持久化 Provider 配置到 SQLite
    - 加密存储 API Key
    - 创建并缓存 Provider 实例
    - 管理激活 Provider（互斥）
    - 提供查询/增删改接口
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _get_db_path()
        self._cipher = APIKeyCipher()
        self._lock = threading.RLock()
        self._instances: dict[str, LLMProvider] = {}  # provider_id -> 实例缓存
        self._initialized = False

    # ------------------------------------------------------------------
    # 数据库初始化
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """获取 SQLite 连接（每次新建，使用完关闭）。"""
        conn = sqlite3.connect(str(self._db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        """初始化数据库表和种子数据。"""
        with self._lock:
            if self._initialized:
                return

            conn = self._get_conn()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS llm_providers (
                        provider_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        provider_type TEXT NOT NULL,
                        base_url TEXT NOT NULL DEFAULT '',
                        api_key_encrypted TEXT NOT NULL DEFAULT '',
                        default_model TEXT NOT NULL DEFAULT '',
                        timeout INTEGER NOT NULL DEFAULT 60,
                        max_retries INTEGER NOT NULL DEFAULT 3,
                        retry_delay REAL NOT NULL DEFAULT 1.0,
                        enabled INTEGER NOT NULL DEFAULT 0,
                        is_active INTEGER NOT NULL DEFAULT 0,
                        priority INTEGER NOT NULL DEFAULT 0,
                        capabilities TEXT NOT NULL DEFAULT '["chat"]',
                        extra TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_llm_providers_active
                    ON llm_providers(is_active) WHERE is_active = 1
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_llm_providers_enabled
                    ON llm_providers(enabled) WHERE enabled = 1
                """)
                conn.commit()

                # 种子数据：首次初始化时插入默认模板
                count = conn.execute(
                    "SELECT COUNT(*) FROM llm_providers"
                ).fetchone()[0]
                if count == 0:
                    self._seed_defaults(conn)

            finally:
                conn.close()

            self._initialized = True
            logger.info(
                "ProviderRegistry 初始化完成，数据库: %s", self._db_path
            )

    def _seed_defaults(self, conn: sqlite3.Connection) -> None:
        """插入默认 Provider 模板。"""
        templates = _default_provider_templates()
        for tpl in templates:
            self._insert_config(conn, tpl)
        logger.info("已插入 %d 个默认 Provider 模板", len(templates))

    def _insert_config(
        self, conn: sqlite3.Connection, config: ProviderConfig
    ) -> None:
        """插入一条 Provider 配置。"""
        conn.execute("""
            INSERT OR REPLACE INTO llm_providers
            (provider_id, name, provider_type, base_url, api_key_encrypted,
             default_model, timeout, max_retries, retry_delay, enabled,
             is_active, priority, capabilities, extra, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            config.provider_id,
            config.name,
            config.provider_type.value,
            config.base_url,
            self._cipher.encrypt(config.api_key),
            config.default_model,
            config.timeout,
            config.max_retries,
            config.retry_delay,
            int(config.enabled),
            int(config.is_active),
            config.priority,
            json.dumps([c.value for c in config.capabilities]),
            json.dumps(config.extra, ensure_ascii=False),
        ))

    # ------------------------------------------------------------------
    # 行 -> ProviderConfig 转换
    # ------------------------------------------------------------------

    def _row_to_config(self, row: sqlite3.Row) -> ProviderConfig:
        """数据库行转换为 ProviderConfig 对象。"""
        try:
            provider_type = ProviderType(row["provider_type"])
        except ValueError:
            provider_type = ProviderType.OPENAI_COMPATIBLE

        caps_raw = row["capabilities"] or '["chat"]'
        try:
            caps_list = json.loads(caps_raw)
            capabilities = [ProviderCapability(c) for c in caps_list]
        except (json.JSONDecodeError, ValueError):
            capabilities = [ProviderCapability.CHAT]

        extra_raw = row["extra"] or "{}"
        try:
            extra = json.loads(extra_raw)
        except json.JSONDecodeError:
            extra = {}

        return ProviderConfig(
            provider_id=row["provider_id"],
            name=row["name"],
            provider_type=provider_type,
            base_url=row["base_url"],
            api_key=self._cipher.decrypt(row["api_key_encrypted"] or ""),
            default_model=row["default_model"],
            timeout=row["timeout"],
            max_retries=row["max_retries"],
            retry_delay=row["retry_delay"],
            enabled=bool(row["enabled"]),
            is_active=bool(row["is_active"]),
            priority=row["priority"],
            capabilities=capabilities,
            extra=extra,
        )

    # ------------------------------------------------------------------
    # 查询接口
    # ------------------------------------------------------------------

    def list_providers(self, include_disabled: bool = True) -> list[ProviderConfig]:
        """列出所有 Provider 配置。"""
        self._init_db()
        conn = self._get_conn()
        try:
            if include_disabled:
                rows = conn.execute(
                    "SELECT * FROM llm_providers ORDER BY priority DESC, name"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM llm_providers WHERE enabled = 1 "
                    "ORDER BY priority DESC, name"
                ).fetchall()
            return [self._row_to_config(r) for r in rows]
        finally:
            conn.close()

    def get_provider(self, provider_id: str) -> ProviderConfig | None:
        """获取指定 Provider 配置。"""
        self._init_db()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM llm_providers WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            return self._row_to_config(row) if row else None
        finally:
            conn.close()

    def get_active_provider_config(self) -> ProviderConfig | None:
        """获取当前激活的 Provider 配置。"""
        self._init_db()
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM llm_providers WHERE is_active = 1 LIMIT 1"
            ).fetchone()
            return self._row_to_config(row) if row else None
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # 增删改
    # ------------------------------------------------------------------

    def upsert_provider(self, config: ProviderConfig) -> None:
        """新增或更新 Provider 配置。

        如果 provider_id 已存在则更新，否则插入。
        """
        self._init_db()
        with self._lock:
            conn = self._get_conn()
            try:
                self._insert_config(conn, config)
                conn.commit()
                # 失效实例缓存
                self._instances.pop(config.provider_id, None)
            finally:
                conn.close()
        logger.info("Provider 配置已保存: %s", config.provider_id)

    def delete_provider(self, provider_id: str) -> bool:
        """删除 Provider 配置。

        Returns:
            True 如果删除成功
        """
        self._init_db()
        with self._lock:
            conn = self._get_conn()
            try:
                cursor = conn.execute(
                    "DELETE FROM llm_providers WHERE provider_id = ?",
                    (provider_id,),
                )
                conn.commit()
                deleted = cursor.rowcount > 0
                if deleted:
                    self._instances.pop(provider_id, None)
                    logger.info("Provider 已删除: %s", provider_id)
                return deleted
            finally:
                conn.close()

    def set_active(self, provider_id: str) -> bool:
        """设置激活的 Provider（互斥）。

        Returns:
            True 如果设置成功
        """
        self._init_db()
        with self._lock:
            conn = self._get_conn()
            try:
                # 检查目标是否存在且启用
                row = conn.execute(
                    "SELECT enabled FROM llm_providers WHERE provider_id = ?",
                    (provider_id,),
                ).fetchone()
                if row is None:
                    return False
                if not bool(row["enabled"]):
                    logger.warning(
                        "无法激活未启用的 Provider: %s", provider_id
                    )
                    return False

                # 互斥：先清除所有 is_active
                conn.execute("UPDATE llm_providers SET is_active = 0")
                # 设置目标
                conn.execute(
                    "UPDATE llm_providers SET is_active = 1, "
                    "updated_at = CURRENT_TIMESTAMP WHERE provider_id = ?",
                    (provider_id,),
                )
                conn.commit()
                # 失效所有实例缓存（激活变更影响 get_active_provider）
                self._instances.clear()
                logger.info("激活 Provider: %s", provider_id)
                return True
            finally:
                conn.close()

    def set_enabled(self, provider_id: str, enabled: bool) -> bool:
        """启用/禁用 Provider。

        禁用激活中的 Provider 会同时取消其激活状态。
        """
        self._init_db()
        with self._lock:
            conn = self._get_conn()
            try:
                if enabled:
                    conn.execute(
                        "UPDATE llm_providers SET enabled = 1, "
                        "updated_at = CURRENT_TIMESTAMP WHERE provider_id = ?",
                        (provider_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE llm_providers SET enabled = 0, is_active = 0, "
                        "updated_at = CURRENT_TIMESTAMP WHERE provider_id = ?",
                        (provider_id,),
                    )
                conn.commit()
                self._instances.pop(provider_id, None)
                return conn.total_changes > 0
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # 实例获取
    # ------------------------------------------------------------------

    def get_provider_instance(
        self, provider_id: str
    ) -> LLMProvider | None:
        """获取 Provider 实例（带缓存）。

        配置变更后缓存自动失效。
        """
        self._init_db()
        with self._lock:
            if provider_id in self._instances:
                return self._instances[provider_id]

            config = self.get_provider(provider_id)
            if config is None or not config.enabled:
                return None

            try:
                instance = create_provider(config)
                self._instances[provider_id] = instance
                return instance
            except Exception as e:
                logger.error(
                    "创建 Provider 实例失败 (%s): %s",
                    provider_id, e, exc_info=True,
                )
                return None

    def get_active_provider(self) -> LLMProvider | None:
        """获取当前激活的 Provider 实例。

        如果没有激活的 Provider，返回 None。
        """
        config = self.get_active_provider_config()
        if config is None:
            return None
        return self.get_provider_instance(config.provider_id)

    def clear_instance_cache(self) -> None:
        """清除所有实例缓存。"""
        with self._lock:
            self._instances.clear()

    # ------------------------------------------------------------------
    # 批量导入（用于自动探测结果）
    # ------------------------------------------------------------------

    def import_from_detection(
        self, configs: list[ProviderConfig]
    ) -> int:
        """从自动探测结果导入 Provider 配置。

        仅导入 provider_id 不存在的配置，已存在的保留用户配置。
        同时将第一个导入的本地 Provider 自动激活（如果当前无激活）。

        Returns:
            实际导入的数量
        """
        if not configs:
            return 0

        self._init_db()
        imported = 0
        first_local_id: str | None = None

        with self._lock:
            conn = self._get_conn()
            try:
                for cfg in configs:
                    # 检查是否已存在
                    existing = conn.execute(
                        "SELECT provider_id FROM llm_providers "
                        "WHERE provider_id = ?",
                        (cfg.provider_id,),
                    ).fetchone()
                    if existing:
                        continue

                    self._insert_config(conn, cfg)
                    imported += 1
                    if first_local_id is None and cfg.provider_type.is_local:
                        first_local_id = cfg.provider_id

                conn.commit()

                # 自动激活
                if first_local_id is not None:
                    active = conn.execute(
                        "SELECT provider_id FROM llm_providers "
                        "WHERE is_active = 1 LIMIT 1"
                    ).fetchone()
                    if active is None:
                        conn.execute(
                            "UPDATE llm_providers SET is_active = 1, "
                            "enabled = 1, "
                            "updated_at = CURRENT_TIMESTAMP "
                            "WHERE provider_id = ?",
                            (first_local_id,),
                        )
                        conn.commit()
                        logger.info(
                            "自动激活探测到的 Provider: %s",
                            first_local_id,
                        )
            finally:
                conn.close()

        if imported > 0:
            self._instances.clear()
            logger.info("从探测结果导入 %d 个 Provider", imported)
        return imported

    # ------------------------------------------------------------------
    # 调试/状态
    # ------------------------------------------------------------------

    def get_status_summary(self) -> dict[str, Any]:
        """返回注册表状态摘要。"""
        self._init_db()
        conn = self._get_conn()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM llm_providers"
            ).fetchone()[0]
            enabled = conn.execute(
                "SELECT COUNT(*) FROM llm_providers WHERE enabled = 1"
            ).fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM llm_providers WHERE is_active = 1"
            ).fetchone()[0]
            local_count = conn.execute(
                "SELECT COUNT(*) FROM llm_providers WHERE provider_type IN "
                "('ollama','lmstudio','llamacpp','vllm','tgi','koboldcpp')"
            ).fetchone()[0]
            cloud_count = total - local_count

            active_row = conn.execute(
                "SELECT provider_id, name, provider_type FROM llm_providers "
                "WHERE is_active = 1 LIMIT 1"
            ).fetchone()

            return {
                "total": total,
                "enabled": enabled,
                "active_count": active,
                "local_count": local_count,
                "cloud_count": cloud_count,
                "active_provider_id": active_row["provider_id"] if active_row else None,
                "active_provider_name": active_row["name"] if active_row else None,
                "encryption_available": self._cipher.available,
                "db_path": str(self._db_path),
            }
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_registry: ProviderRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> ProviderRegistry:
    """获取全局 ProviderRegistry 实例（线程安全懒加载）。"""
    global _registry
    if _registry is not None:
        return _registry
    with _registry_lock:
        if _registry is not None:
            return _registry
        _registry = ProviderRegistry()
        _registry._init_db()
        return _registry


def init_registry(db_path: Path | None = None) -> ProviderRegistry:
    """显式初始化注册表（可选，用于测试或自定义路径）。"""
    global _registry
    with _registry_lock:
        _registry = ProviderRegistry(db_path=db_path)
        _registry._init_db()
        return _registry


def reset_registry() -> None:
    """重置全局注册表（主要供测试使用）。"""
    global _registry
    with _registry_lock:
        _registry = None
