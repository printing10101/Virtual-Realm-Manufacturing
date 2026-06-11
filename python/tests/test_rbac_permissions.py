"""
Test RBAC Permission Check Core Logic

Tests for:
- RBACPermissionCache: caching, invalidation, TTL behavior
- check_user_has_permission: single permission check
- check_user_has_any_permission: OR logic permission check
- check_user_has_all_permissions: AND logic permission check
- Pydantic models: RoleResponse, PermissionResponse, UserListItem, etc.
"""

from __future__ import annotations

import time
import pytest
from unittest.mock import patch, MagicMock


class TestRBACPermissionCache:
    """Test RBACPermissionCache singleton and caching behavior"""

    def test_singleton_behavior(self):
        from app.auth.permissions import RBACPermissionCache

        cache1 = RBACPermissionCache()
        cache2 = RBACPermissionCache()
        assert cache1 is cache2

    def test_get_miss_returns_none(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        result = rbac_cache.get("nonexistent_role")
        assert result is None

    def test_set_and_get(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        perms = {"project:create", "result:view"}
        rbac_cache.set("engineer", perms)

        result = rbac_cache.get("engineer")
        assert result == perms

    def test_ttl_expiry(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        rbac_cache._ttl = 0.001
        rbac_cache.set("temp_role", {"result:view"})
        time.sleep(0.01)

        result = rbac_cache.get("temp_role")
        assert result is None

    def test_invalidate_specific_role(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        rbac_cache._ttl = 3600
        rbac_cache.set("admin", {"system:config"})
        rbac_cache.set("engineer", {"project:create"})

        rbac_cache.invalidate("admin")
        assert rbac_cache.get("admin") is None
        assert rbac_cache.get("engineer") == {"project:create"}

    def test_invalidate_all_roles(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        rbac_cache._ttl = 3600
        rbac_cache.set("admin", {"system:config"})
        rbac_cache.set("engineer", {"project:create"})

        rbac_cache.invalidate()
        assert rbac_cache.get("admin") is None
        assert rbac_cache.get("engineer") is None

    def test_ttl_restored_after_test(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._ttl = 60.0
        rbac_cache._cache.clear()


class TestCheckUserPermissions:
    """Test permission check functions"""

    @pytest.fixture(autouse=True)
    def setup_cache(self):
        from app.auth.permissions import rbac_cache

        rbac_cache._cache.clear()
        rbac_cache._ttl = 3600
        yield
        rbac_cache._cache.clear()
        rbac_cache._ttl = 60.0

    @pytest.mark.asyncio
    async def test_check_user_has_permission_granted(self):
        from app.auth.permissions import (
            check_user_has_permission,
            rbac_cache,
        )

        rbac_cache.set("admin", {"system:config", "user:manage"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "admin"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_permission("test_user", "system:config")
            assert result is True

    @pytest.mark.asyncio
    async def test_check_user_has_permission_denied(self):
        from app.auth.permissions import (
            check_user_has_permission,
            rbac_cache,
        )

        rbac_cache.set("operator", {"result:view", "report:export"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_permission("test_user", "system:config")
            assert result is False

    @pytest.mark.asyncio
    async def test_check_user_has_permission_user_not_found(self):
        from app.auth.permissions import check_user_has_permission

        with patch("app.models.user.get_user_store") as mock_store:
            mock_store.return_value.get_user.return_value = None

            result = await check_user_has_permission("unknown_user", "any:perm")
            assert result is False

    @pytest.mark.asyncio
    async def test_check_user_has_any_permission_single_match(self):
        from app.auth.permissions import (
            check_user_has_any_permission,
            rbac_cache,
        )

        rbac_cache.set("engineer", {"project:create", "simulation:run"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_any_permission(
                "test_user", ["system:config", "project:create"]
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_user_has_any_permission_no_match(self):
        from app.auth.permissions import (
            check_user_has_any_permission,
            rbac_cache,
        )

        rbac_cache.set("operator", {"result:view"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_any_permission(
                "test_user", ["system:config", "user:manage"]
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_check_user_has_any_permission_empty_list(self):
        from app.auth.permissions import (
            check_user_has_any_permission,
            rbac_cache,
        )

        rbac_cache.set("engineer", {"project:create"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_any_permission("test_user", [])
            assert result is False

    @pytest.mark.asyncio
    async def test_check_user_has_all_permissions_all_match(self):
        from app.auth.permissions import (
            check_user_has_all_permissions,
            rbac_cache,
        )

        rbac_cache.set("admin", {"system:config", "user:manage", "project:create"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "admin"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_all_permissions(
                "test_user", ["system:config", "user:manage"]
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_user_has_all_permissions_partial_match(self):
        from app.auth.permissions import (
            check_user_has_all_permissions,
            rbac_cache,
        )

        rbac_cache.set("engineer", {"project:create", "simulation:run"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_all_permissions(
                "test_user", ["project:create", "system:config"]
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_check_user_has_all_permissions_single(self):
        from app.auth.permissions import (
            check_user_has_all_permissions,
            rbac_cache,
        )

        rbac_cache.set("operator", {"result:view"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_all_permissions(
                "test_user", ["result:view"]
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_check_user_has_all_permissions_empty_list(self):
        from app.auth.permissions import (
            check_user_has_all_permissions,
            rbac_cache,
        )

        rbac_cache.set("engineer", {"project:create"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            result = await check_user_has_all_permissions("test_user", [])
            assert result is True


class TestAdminRolePermissions:
    """Test admin role has all permissions"""

    @pytest.mark.asyncio
    async def test_admin_can_access_all_permissions(self):
        from app.auth.permissions import (
            check_user_has_permission,
            check_user_has_all_permissions,
            rbac_cache,
        )

        all_perms = {
            "system:config", "user:manage", "project:create", "project:delete",
            "simulation:run", "simulation:configure", "result:view", "report:export",
            "model:train", "model:predict", "rule:edit", "toolpath:edit",
        }
        rbac_cache.set("admin", all_perms)

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "admin"
            mock_store.return_value.get_user.return_value = mock_user

            for perm in all_perms:
                assert await check_user_has_permission("admin_user", perm) is True

            assert await check_user_has_all_permissions("admin_user", list(all_perms)) is True


class TestEngineerRolePermissions:
    """Test engineer role has correct permissions"""

    @pytest.mark.asyncio
    async def test_engineer_can_create_project(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("engineer", {"project:create", "simulation:run", "result:view", "report:export", "model:predict", "rule:edit", "toolpath:edit"})  # noqa: E501

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("eng_user", "project:create") is True

    @pytest.mark.asyncio
    async def test_engineer_can_run_simulation(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("engineer", {"project:create", "simulation:run", "result:view", "report:export", "model:predict", "rule:edit", "toolpath:edit"})  # noqa: E501

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("eng_user", "simulation:run") is True

    @pytest.mark.asyncio
    async def test_engineer_cannot_manage_users(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("engineer", {"project:create", "simulation:run", "result:view"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("eng_user", "user:manage") is False

    @pytest.mark.asyncio
    async def test_engineer_cannot_configure_system(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("engineer", {"project:create", "simulation:run"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("eng_user", "system:config") is False


class TestOperatorRolePermissions:
    """Test operator role has correct permissions"""

    @pytest.mark.asyncio
    async def test_operator_can_view_results(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("operator", {"result:view", "report:export", "model:predict"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("op_user", "result:view") is True

    @pytest.mark.asyncio
    async def test_operator_can_export_reports(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("operator", {"result:view", "report:export", "model:predict"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("op_user", "report:export") is True

    @pytest.mark.asyncio
    async def test_operator_cannot_create_project(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("operator", {"result:view", "report:export"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("op_user", "project:create") is False

    @pytest.mark.asyncio
    async def test_operator_cannot_run_simulation(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("operator", {"result:view", "report:export"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("op_user", "simulation:run") is False

    @pytest.mark.asyncio
    async def test_operator_cannot_manage_users(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        rbac_cache.set("operator", {"result:view", "report:export"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("op_user", "user:manage") is False


class TestPermissionBoundaryCrossRole:
    """Test permission boundaries between different roles"""

    @pytest.mark.asyncio
    async def test_operator_boundary_vs_engineer_permissions(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        operator_perms = {"result:view", "report:export", "model:predict"}
        engineer_only_perms = {"project:create", "simulation:run", "rule:edit", "toolpath:edit"}

        rbac_cache.set("operator", operator_perms)

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "operator"
            mock_store.return_value.get_user.return_value = mock_user

            for perm in engineer_only_perms:
                assert await check_user_has_permission("op_user", perm) is False

    @pytest.mark.asyncio
    async def test_engineer_boundary_vs_admin_permissions(self):
        from app.auth.permissions import check_user_has_permission, rbac_cache

        engineer_perms = {"project:create", "simulation:run", "result:view", "report:export", "model:predict", "rule:edit", "toolpath:edit"}  # noqa: E501
        admin_only_perms = {"system:config", "user:manage", "project:delete", "simulation:configure", "model:train"}

        rbac_cache.set("engineer", engineer_perms)

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            for perm in admin_only_perms:
                assert await check_user_has_permission("eng_user", perm) is False


class TestGetUserPermissions:
    """Test get_user_permissions function"""

    @pytest.mark.asyncio
    async def test_get_user_permissions_with_db(self):
        from app.auth.permissions import get_user_permissions, rbac_cache

        rbac_cache.set("admin", {"system:config"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "admin"
            mock_store.return_value.get_user.return_value = mock_user

            perms = await get_user_permissions("admin_user")
            assert perms == {"system:config"}

    @pytest.mark.asyncio
    async def test_get_user_permissions_user_not_found(self):
        from app.auth.permissions import get_user_permissions

        with patch("app.models.user.get_user_store") as mock_store:
            mock_store.return_value.get_user.return_value = None

            perms = await get_user_permissions("ghost_user")
            assert perms == set()


class TestPydanticSchemas:
    """Test Pydantic RBAC schemas"""

    def test_role_response_creation(self):
        from app.models.schemas import RoleResponse

        role = RoleResponse(id=1, name="管理员", code="admin", description="系统管理员")
        assert role.id == 1
        assert role.name == "管理员"
        assert role.code == "admin"
        assert role.description == "系统管理员"

    def test_permission_response_creation(self):
        from app.models.schemas import PermissionResponse

        perm = PermissionResponse(id=1, name="用户管理", code="user:manage")
        assert perm.id == 1
        assert perm.code == "user:manage"

    def test_role_detail_response_with_permissions(self):
        from app.models.schemas import RoleDetailResponse, PermissionResponse

        perms = [PermissionResponse(id=1, name="用户管理", code="user:manage")]
        role = RoleDetailResponse(id=1, name="管理员", code="admin", permissions=perms)
        assert len(role.permissions) == 1
        assert role.permissions[0].code == "user:manage"

    def test_role_detail_response_default_permissions(self):
        from app.models.schemas import RoleDetailResponse

        role = RoleDetailResponse(id=1, name="Test", code="test")
        assert role.permissions == []

    def test_role_assign_request(self):
        from app.models.schemas import RoleAssignRequest

        req = RoleAssignRequest(role_code="engineer")
        assert req.role_code == "engineer"

    def test_user_status_request(self):
        from app.models.schemas import UserStatusRequest

        req = UserStatusRequest(is_active=True)
        assert req.is_active is True

        req2 = UserStatusRequest(is_active=False)
        assert req2.is_active is False

    def test_user_list_item(self):
        from app.models.schemas import UserListItem

        item = UserListItem(username="test_user", role="admin", is_active=True)
        assert item.username == "test_user"
        assert item.role == "admin"
        assert item.is_active is True

    def test_user_list_response(self):
        from app.models.schemas import UserListResponse, UserListItem

        users = [
            UserListItem(username="u1", role="admin", is_active=True),
            UserListItem(username="u2", role="engineer", is_active=True),
        ]
        resp = UserListResponse(total=2, users=users)
        assert resp.total == 2
        assert len(resp.users) == 2

    def test_permission_check_result(self):
        from app.models.schemas import PermissionCheckResult

        result = PermissionCheckResult(has_permission=True, user_permissions=["project:create"])
        assert result.has_permission is True
        assert result.user_permissions == ["project:create"]

    def test_role_assign_request_missing_code_raises_error(self):
        from pydantic import ValidationError
        from app.models.schemas import RoleAssignRequest

        with pytest.raises(ValidationError):
            RoleAssignRequest()

    def test_user_status_request_missing_field_raises_error(self):
        from pydantic import ValidationError
        from app.models.schemas import UserStatusRequest

        with pytest.raises(ValidationError):
            UserStatusRequest()


class TestPermissionCacheRealTimeInvalidation:
    """Test that permission cache invalidation works for real-time updates"""

    @pytest.mark.asyncio
    async def test_role_change_invalidates_cache(self):
        from app.auth.permissions import (
            get_user_permissions,
            check_user_has_permission,
            rbac_cache,
        )

        rbac_cache.set("engineer", {"project:create", "simulation:run"})

        with patch("app.models.user.get_user_store") as mock_store:
            mock_user = MagicMock()
            mock_user.role = "engineer"
            mock_store.return_value.get_user.return_value = mock_user

            assert await check_user_has_permission("test_user", "project:create") is True

            rbac_cache.invalidate("engineer")
            rbac_cache.set("operator", {"result:view"})
            mock_user.role = "operator"

            perms = await get_user_permissions("test_user")
            assert perms == {"result:view"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
