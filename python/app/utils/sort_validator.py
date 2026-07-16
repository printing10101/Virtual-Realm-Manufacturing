"""统一的排序字段白名单校验工具。

防止 SQL 注入：当排序字段通过列名拼接进 SQL 时，必须经过白名单校验。
本模块提供统一的校验入口，供所有需要 sort_by 参数的 API 复用。
"""

from __future__ import annotations

from fastapi import HTTPException


def validate_sort_field(
    field: str,
    allowed: set[str],
    default: str = "created_at",
) -> str:
    """校验排序字段是否在白名单中。

    Args:
        field: 前端传入的排序字段名。
        allowed: 允许的排序字段白名单集合。
        default: 当 ``field`` 为空字符串时的默认值（不在白名单时不回退，
            而是抛 400，避免静默吞掉非法输入）。

    Returns:
        校验通过的安全排序字段名。

    Raises:
        HTTPException: 当 ``field`` 不在 ``allowed`` 白名单中时，抛出 400。
    """
    if not field:
        field = default

    if field not in allowed:
        raise HTTPException(
            status_code=400,
            detail=(
                f"不支持的排序字段: {field}，"
                f"允许: {', '.join(sorted(allowed))}"
            ),
        )

    return field


def validate_sort_order(order: str, default: str = "DESC") -> str:
    """校验排序方向（ASC / DESC）。

    Args:
        order: 前端传入的排序方向。
        default: 当 ``order`` 为空字符串时的默认值。

    Returns:
        大写的排序方向（``"ASC"`` 或 ``"DESC"``）。

    Raises:
        HTTPException: 当 ``order`` 不是 ASC / DESC 时，抛出 400。
    """
    if not order:
        order = default

    upper = order.upper()
    if upper not in {"ASC", "DESC"}:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的排序方向: {order}，仅支持 ASC / DESC",
        )

    return upper


__all__ = ["validate_sort_field", "validate_sort_order"]
