"""方言注册表：扫描本地插件目录，编译声明并注册到 PostProcessorRegistry。

对应 docs/development/postprocessor-方言声明化设计.md §3.2/§3.5：
- 扫描 ``<plugin_root>/*/dialect.yaml``
- 解析 extends 继承链（当前一层），编译为方言类
- 注册到 ``PostProcessorRegistry``（register 钩子已存在，registry.py:83）
- 查询优先级：方言注册表优先，未命中回退内置类 → ``load_from_config`` 调用方零改动
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.dialect.compiler import DialectCompiler, DialectCompileError
from app.postprocessor.dialect.declaration import (
    DialectDeclaration,
    DialectDeclarationError,
)
from app.postprocessor.registry import PostProcessorRegistry

logger = logging.getLogger(__name__)

# 默认本地方言插件根目录（相对仓库根；可通过构造参数覆盖）
DEFAULT_DIALECT_PLUGIN_DIR = "postprocessor-plugins"


class DialectRegistry:
    """本地方言插件注册表。

    生命周期：
    - ``discover()``：扫描插件目录，加载并校验声明
    - ``compile_all()``：编译全部声明为方言类
    - ``register_to()``：注册到 PostProcessorRegistry（含参数默认值）

    使用示例::

        registry = DialectRegistry(plugin_root="postprocessor-plugins")
        count = registry.discover()
        registry.compile_all()
        registry.register_to(PostProcessorRegistry())
    """

    def __init__(
        self,
        plugin_root: Optional[str | Path] = None,
        compiler: Optional[DialectCompiler] = None,
    ) -> None:
        self.plugin_root = Path(plugin_root) if plugin_root else Path(DEFAULT_DIALECT_PLUGIN_DIR)
        self.compiler = compiler or DialectCompiler()
        self._declarations: Dict[str, DialectDeclaration] = {}
        self._compiled_classes: Dict[str, Type[BasePostProcessor]] = {}
        self._compile_errors: Dict[str, str] = {}

    # ------------------------------------------------------------------
    # 发现 / 编译 / 注册
    # ------------------------------------------------------------------

    def discover(self) -> List[str]:
        """扫描插件目录下的方言声明，返回发现的方言 id 列表。

        单目录声明失败仅记录错误并跳过（与其他插件失败降级策略一致），
        不阻断整体发现。
        """
        self._declarations.clear()
        self._compile_errors.clear()

        if not self.plugin_root.exists():
            logger.warning("方言插件目录不存在: %s", self.plugin_root)
            return []

        found: List[str] = []
        for item in sorted(self.plugin_root.iterdir()):
            if not item.is_dir():
                continue
            declaration_path = item / "dialect.yaml"
            if not declaration_path.exists():
                logger.debug("跳过非方言目录: %s（无 dialect.yaml）", item)
                continue
            try:
                declaration = DialectDeclaration.from_yaml(declaration_path)
            except DialectDeclarationError as e:
                logger.error("方言声明加载失败: %s", e)
                self._compile_errors[item.name] = str(e)
                continue
            self._declarations[declaration.id] = declaration
            found.append(declaration.id)
            logger.info("发现方言: %s v%s (extends=%s)", declaration.id, declaration.version, declaration.extends)

        return found

    def compile_all(self) -> Dict[str, Type[BasePostProcessor]]:
        """编译全部已发现声明为方言类。

        Returns:
            {方言 id: 编译后的类}（仅成功项）

        Raises:
            DialectCompileError: 任一声明编译失败（fail-fast，声明错误必须暴露）
        """
        for dialect_id, declaration in self._declarations.items():
            try:
                self._compiled_classes[dialect_id] = self.compiler.compile(declaration)
            except DialectCompileError as e:
                logger.error("方言编译失败: %s", e)
                self._compile_errors[dialect_id] = str(e)
                raise
        return dict(self._compiled_classes)

    def register_to(self, target: Optional[PostProcessorRegistry] = None) -> int:
        """把编译后的方言注册到 PostProcessorRegistry。

        Args:
            target: 目标注册表；None 时使用 PostProcessorRegistry 单例

        Returns:
            成功注册的方言数

        Raises:
            DialectCompileError: 存在未编译的声明（应先调用 compile_all）
        """
        registry = target or PostProcessorRegistry()

        # 确保已编译
        uncompile = [i for i in self._declarations if i not in self._compiled_classes]
        if uncompile:
            raise DialectCompileError(
                f"存在未编译的方言声明: {uncompile}。建议操作：先调用 compile_all()。"
            )

        count = 0
        for dialect_id, cls in self._compiled_classes.items():
            # 方言注册优先：覆盖同 id 的内置注册（register 允许覆盖）
            registry.register(dialect_id, cls)
            count += 1
            logger.info("方言已注册到 PostProcessorRegistry: %s -> %s", dialect_id, cls.__name__)
        return count

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_dialects(self) -> List[str]:
        """列出已发现（含编译失败）的方言 id。"""
        return sorted(self._declarations.keys())

    def get_declaration(self, dialect_id: str) -> Optional[DialectDeclaration]:
        return self._declarations.get(dialect_id)

    def get_compile_errors(self) -> Dict[str, str]:
        """返回 {方言 id/目录名: 错误信息}（含加载与编译失败）。"""
        return dict(self._compile_errors)


def load_dialects(
    plugin_root: Optional[str | Path] = None,
    target: Optional[PostProcessorRegistry] = None,
) -> int:
    """便捷入口：发现 + 编译 + 注册一次完成。

    Args:
        plugin_root: 本地方言插件根目录（默认 postprocessor-plugins/）
        target: 目标注册表（默认 PostProcessorRegistry 单例）

    Returns:
        成功注册的方言数
    """
    registry = DialectRegistry(plugin_root=plugin_root)
    registry.discover()
    registry.compile_all()
    return registry.register_to(target)


__all__ = ["DEFAULT_DIALECT_PLUGIN_DIR", "DialectRegistry", "load_dialects"]
