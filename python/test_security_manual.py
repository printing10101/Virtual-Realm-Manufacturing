from app.core.permissions import (
    PermissionLevel,
    permission_checker,
    paper_only_guard,
)

# Test 5: Permission granularity
print("=" * 60)
print("TEST 5: Permission Granularity Control")
print("=" * 60)

print("\nR-level token access tests:")
print(
    f"  R -> GET /api/v1/lnn/models (R endpoint): {permission_checker.has_permission(PermissionLevel.R, '/api/v1/lnn/models', 'GET')} (expected: True)"
)
print(
    f"  R -> POST /api/v1/lnn/train (B endpoint): {permission_checker.has_permission(PermissionLevel.R, '/api/v1/lnn/train', 'POST')} (expected: False)"
)
print(
    f"  R -> POST /api/v1/machine/execute (T endpoint): {permission_checker.has_permission(PermissionLevel.R, '/api/v1/machine/execute', 'POST')} (expected: False)"
)

print("\nT-level token access tests:")
print(
    f"  T -> POST /api/v1/lnn/train (B endpoint): {permission_checker.has_permission(PermissionLevel.T, '/api/v1/lnn/train', 'POST')} (expected: True)"
)
print(
    f"  T -> POST /api/v1/machine/execute (T endpoint): {permission_checker.has_permission(PermissionLevel.T, '/api/v1/machine/execute', 'POST')} (expected: True)"
)

# Test 6: Paper-Only mode
print("\n" + "=" * 60)
print("TEST 6: Paper-Only Mode Control")
print("=" * 60)
print(f"  LNN_LIVE_EXECUTION_ENABLED env: {paper_only_guard.live_execution_enabled}")
print(
    f"  Live execution allowed: {paper_only_guard.is_live_execution_allowed()} (expected: False)"
)

result, msg = paper_only_guard.check_t_operation(True, True)
print(
    f"  T operation (with T permission + UI confirm): {result} - {msg} (expected: False - Paper-Only)"
)

sim = paper_only_guard.simulate_t_operation(
    {"machine": "cnc01", "params": {"speed": 1000}}
)
print(f"  Simulated T operation status: {sim['status']} (expected: simulated)")
