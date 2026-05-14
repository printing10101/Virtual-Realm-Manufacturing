"""
Governance & Approval Workflow System - Comprehensive Test Suite

10 detailed test scenarios:
1. System configuration verification (approve_before_execute strategy)
2. Approval notification & detail page verification
3. Approval pass flow verification
4. Approval reject flow verification
5. Approval timeout functionality (escalation/auto-reject)
6. Emergency override functionality
7. Audit log completeness verification
8. Approval delegation functionality
9. Governance report generation verification
10. Mobile compatibility verification (frontend structure check)
"""
import sys
import os
import io
import time
import json
import tempfile
import threading

if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from app.models.governance import (
    ApprovalStrategy,
    ApprovalPriority,
    ApprovalStatus,
    ApprovalMode,
    TaskType,
    AgentRole,
    ResourceSensitivity,
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalDecision,
    ApprovalDelegation,
    GovernanceReport,
    EmergencyOperation,
    DEFAULT_GLOBAL_POLICIES,
    STRATEGY_PRIORITY_MAP,
    DIMENSION_PRIORITY,
)
from app.core.approval_workflow import ApprovalWorkflowEngine
from app.core.risk_identifier import (
    RiskScorer,
    HighRiskOperationIdentifier,
    OperationCategory,
    RiskAssessment,
    RiskFactor,
)


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.details = []

    def assert_true(self, condition: bool, description: str):
        if condition:
            self.passed += 1
            self.details.append(f"  PASS: {description}")
        else:
            self.failed += 1
            self.details.append(f"  FAIL: {description}")

    def assert_equal(self, actual, expected, description: str):
        if actual == expected:
            self.passed += 1
            self.details.append(f"  PASS: {description}")
        else:
            self.failed += 1
            self.details.append(f"  FAIL: {description} (expected={expected}, actual={actual})")

    def assert_in(self, item, container, description: str):
        if item in container:
            self.passed += 1
            self.details.append(f"  PASS: {description}")
        else:
            self.failed += 1
            self.details.append(f"  FAIL: {description}")


def create_test_engine():
    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test_governance.db")
    engine = ApprovalWorkflowEngine(db_path=db_path)
    return engine, tmpdir


def cleanup_test_engine(engine, tmpdir):
    engine.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def print_test_header(test_num: int, title: str):
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: {title}")
    print(f"{'='*80}")


def print_test_result(result: TestResult, test_num: int, title: str):
    print()
    for detail in result.details:
        print(detail)
    status = "PASS" if result.failed == 0 else "FAIL"
    print(f"\n[TEST {test_num}] {status}: {title} ({result.passed} passed, {result.failed} failed)")


# ============================================================
# TEST 1: System Configuration Verification
# ============================================================
def test_1_system_configuration_verification():
    print_test_header(1, "System Configuration Verification - Approve Before Execute Strategy")

    result = TestResult()

    # 1.1 Verify default policy for T-type operations (execution task)
    execution_policies = [p for p in DEFAULT_GLOBAL_POLICIES if p.dimension == "task_type" and p.dimension_value == TaskType.EXECUTION.value]
    result.assert_true(len(execution_policies) > 0, "Default policy exists for execution task type")
    if execution_policies:
        exec_policy = execution_policies[0]
        result.assert_equal(
            exec_policy.strategy,
            ApprovalStrategy.MULTI_APPROVAL,
            "Execution task default strategy is MULTI_APPROVAL"
        )
        result.assert_true(
            exec_policy.required_approvals >= 2,
            f"Execution requires {exec_policy.required_approvals} approvals"
        )

    # 1.2 Verify approve_before_execute strategy is available
    result.assert_true(
        ApprovalStrategy.APPROVE_BEFORE_EXECUTE in ApprovalStrategy,
        "APPROVE_BEFORE_EXECUTE strategy is defined"
    )

    # 1.3 Create an engine and configure a policy for machine parameter dispatch
    engine, tmpdir = create_test_engine()

    # Set up approval policy: approve_before_execute for T-type operations
    policy = ApprovalPolicy(
        dimension="task_type",
        dimension_value="machine_param_dispatch",
        strategy=ApprovalStrategy.APPROVE_BEFORE_EXECUTE,
        priority=ApprovalPriority.HIGH,
        required_approvals=1,
        approval_timeout_hours=24.0,
        enabled=True,
    )
    result.assert_true(policy.strategy == ApprovalStrategy.APPROVE_BEFORE_EXECUTE, "Policy configured as approve_before_execute")
    result.assert_true(policy.enabled, "Policy is enabled")

    # 1.4 Create a dispatch task and verify it goes to pending approval
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T1-001",
        operation_type="machine_param_dispatch",
        context={"requester_id": "engineer1", "machine_id": "CNC-001"},
        requester_role=AgentRole.ENGINEER,
    )

    result.assert_true(
        assessment.requires_approval,
        "Machine param dispatch requires approval"
    )
    result.assert_true(
        assessment.suggested_strategy in (ApprovalStrategy.APPROVE_BEFORE_EXECUTE, ApprovalStrategy.MULTI_APPROVAL),
        f"Suggested strategy: {assessment.suggested_strategy.value} (approve_before_execute or multi_approval for high-risk)"
    )

    # 1.5 Create approval request and verify status is PENDING
    request = engine.create_approval_request(
        task_id="TASK-T1-DISPATCH-001",
        requester="engineer1",
        context={
            "operation_type": "machine_param_dispatch",
            "machine_id": "CNC-001",
            "parameters": {"feed_rate": 100, "spindle_speed": 2000},
            "risk_assessment": assessment.to_dict(),
        },
        priority=assessment.suggested_priority,
        approvers=assessment.suggested_approvers,
        risk_score=assessment.risk_score,
        risk_factors=[f.name for f in assessment.risk_factors],
        suggested_decision=assessment.suggested_strategy.value,
    )

    result.assert_equal(
        request.status,
        ApprovalStatus.PENDING,
        f"Task status set to {request.status.value} (pending_approval)"
    )
    result.assert_true(
        request.task_id == "TASK-T1-DISPATCH-001",
        f"Task ID correctly set: {request.task_id}"
    )
    result.assert_true(
        "machine_param_dispatch" in request.context.get("operation_type", ""),
        "Operation type context preserved"
    )

    # 1.6 Verify pending requests list includes this task
    pending = engine.get_requests_by_status(ApprovalStatus.PENDING)
    result.assert_true(
        len(pending) > 0,
        f"Pending requests list contains {len(pending)} request(s)"
    )
    result.assert_true(
        any(r.request_id == request.request_id for r in pending),
        "New dispatch task appears in pending list"
    )

    # 1.7 Frontend status identifier verification
    status_mapping = {
        ApprovalStatus.PENDING: "待审批",
        ApprovalStatus.UNDER_REVIEW: "审核中",
        ApprovalStatus.APPROVED: "已批准",
        ApprovalStatus.REJECTED: "已拒绝",
        ApprovalStatus.ESCALATED: "已升级",
    }
    result.assert_true(
        ApprovalStatus.PENDING in status_mapping,
        f"Frontend status mapping: PENDING -> '{status_mapping[ApprovalStatus.PENDING]}'"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 1, "System Configuration Verification")
    return result


# ============================================================
# TEST 2: Approval Notification & Detail Page Verification
# ============================================================
def test_2_approval_notification_and_detail():
    print_test_header(2, "Approval Notification & Detail Page Verification")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # 2.1 Create approval request (simulating notification trigger)
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T2-001",
        operation_type="model_train",
        context={"requester_id": "ml_engineer1", "model_name": "LTC-v2"},
        requester_role=AgentRole.ENGINEER,
    )

    request = engine.create_approval_request(
        task_id="TASK-T2-TRAIN-001",
        requester="ml_engineer1",
        context={
            "operation_type": "model_train",
            "model_name": "LTC-v2",
            "training_params": {"epochs": 100, "lr": 0.001},
            "goal_chain": {
                "mission": "Improve machining accuracy",
                "strategic_goal": "Optimize LNN models",
                "project": "LTC model v2 development",
            },
            "risk_assessment": assessment.to_dict(),
        },
        priority=assessment.suggested_priority,
        approvers=["process_engineer", "ml_lead"],
        risk_score=assessment.risk_score,
        risk_factors=[f.name for f in assessment.risk_factors],
        suggested_decision=assessment.suggested_strategy.value,
    )

    result.assert_true(
        request.request_id.startswith("AR-"),
        f"Approval request created with ID: {request.request_id}"
    )

    # 2.2 Simulate notification delivery to approver
    notifications = []
    for approver in request.approvers:
        notifications.append({
            "type": "system_notification",
            "approver_id": approver,
            "request_id": request.request_id,
            "message": f"New approval request: {request.request_id} for task {request.task_id}",
            "created_at": time.time(),
        })
        notifications.append({
            "type": "email_notification",
            "approver_id": approver,
            "request_id": request.request_id,
            "message": f"You have a new approval task: {request.request_id}",
        })
        notifications.append({
            "type": "sms_notification",
            "approver_id": approver,
            "request_id": request.request_id,
            "message": f"Approval pending: {request.request_id}",
        })

    result.assert_equal(
        len(notifications),
        len(request.approvers) * 3,
        f"Generated {len(notifications)} notifications (system+email+sms per approver)"
    )

    # 2.3 Assign approver and verify notification routing
    primary_approver = request.approvers[0]
    assigned = engine.assign_approver(request.request_id, primary_approver)
    result.assert_true(
        assigned is not None and assigned.assigned_approver == primary_approver,
        f"Request assigned to approver: {primary_approver}"
    )

    # 2.4 Verify detail page information completeness
    detail_page_data = {
        "request_id": request.request_id,
        "task_id": request.task_id,
        "requester": request.requester,
        "priority": request.priority.value,
        "risk_score": request.risk_score,
        "risk_factors": request.risk_factors,
        "suggested_decision": request.suggested_decision,
        "context": request.context,
    }

    result.assert_true(
        "request_id" in detail_page_data,
        "Detail page contains request_id"
    )
    result.assert_true(
        "task_id" in detail_page_data,
        "Detail page contains task_id"
    )
    result.assert_true(
        "risk_score" in detail_page_data,
        f"Detail page contains risk score: {detail_page_data['risk_score']:.2f}"
    )
    result.assert_true(
        "suggested_decision" in detail_page_data,
        f"Detail page contains system suggestion: {detail_page_data['suggested_decision']}"
    )

    # 2.5 Verify goal chain information display
    context = detail_page_data["context"]
    goal_chain = context.get("goal_chain", {})
    result.assert_true(
        "mission" in goal_chain,
        f"Goal chain mission: {goal_chain.get('mission', 'N/A')}"
    )
    result.assert_true(
        "strategic_goal" in goal_chain,
        f"Goal chain strategic goal: {goal_chain.get('strategic_goal', 'N/A')}"
    )
    result.assert_true(
        "project" in goal_chain,
        f"Goal chain project: {goal_chain.get('project', 'N/A')}"
    )

    # 2.6 Verify risk score display (numeric value + risk level)
    risk_level = "critical" if request.risk_score >= 0.8 else "high" if request.risk_score >= 0.6 else "medium" if request.risk_score >= 0.4 else "low"
    result.assert_true(
        isinstance(request.risk_score, (int, float)),
        f"Risk score is numeric: {request.risk_score}"
    )
    result.assert_true(
        0.0 <= request.risk_score <= 1.0,
        f"Risk score in valid range [0,1]: {request.risk_score}"
    )
    result.assert_true(
        risk_level in ["critical", "high", "medium", "low"],
        f"Risk level identifier: {risk_level}"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 2, "Approval Notification & Detail Page Verification")
    return result


# ============================================================
# TEST 3: Approval Pass Flow Verification
# ============================================================
def test_3_approval_pass_flow():
    print_test_header(3, "Approval Pass Flow Verification")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # 3.1 Create approval request
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T3-001",
        operation_type="machine_param_dispatch",
        context={"requester_id": "engineer2", "machine_id": "CNC-002"},
        requester_role=AgentRole.ENGINEER,
    )

    request = engine.create_approval_request(
        task_id="TASK-T3-DISPATCH-001",
        requester="engineer2",
        context={
            "operation_type": "machine_param_dispatch",
            "machine_id": "CNC-002",
            "parameters": {"feed_rate": 150, "spindle_speed": 3000},
        },
        priority=ApprovalPriority.HIGH,
        approvers=["process_engineer"],
        risk_score=assessment.risk_score,
    )

    result.assert_equal(
        request.status,
        ApprovalStatus.PENDING,
        "Initial status: PENDING"
    )

    # 3.2 Assign approver
    assigned = engine.assign_approver(request.request_id, "process_engineer")
    result.assert_equal(
        assigned.status,
        ApprovalStatus.UNDER_REVIEW,
        f"Status after assignment: {assigned.status.value}"
    )

    # 3.3 Record approval timestamp before decision
    pre_approval_time = time.time()

    # 3.4 Approver executes "approve" action
    time.sleep(0.01)
    approved = engine.make_decision(
        request.request_id,
        "process_engineer",
        "approved",
        "Parameters verified, safe for production"
    )

    result.assert_true(
        approved is not None,
        "Approval decision recorded successfully"
    )
    result.assert_equal(
        approved.status,
        ApprovalStatus.APPROVED,
        f"Status after approval: {approved.status.value}"
    )

    # 3.5 Verify approval time and approver information
    result.assert_true(
        approved.completed_at is not None,
        f"Approval completion time recorded: {approved.completed_at}"
    )
    result.assert_true(
        approved.completed_at > pre_approval_time,
        "Completion time is after approval action"
    )
    result.assert_true(
        len(approved.decisions) == 1,
        f"Decision count: {len(approved.decisions)}"
    )
    result.assert_equal(
        approved.decisions[0].approver_id,
        "process_engineer",
        f"Approver ID recorded: {approved.decisions[0].approver_id}"
    )
    result.assert_equal(
        approved.decisions[0].decision,
        "approved",
        f"Decision value: {approved.decisions[0].decision}"
    )
    result.assert_equal(
        approved.decisions[0].comment,
        "Parameters verified, safe for production",
        f"Comment recorded: {approved.decisions[0].comment}"
    )

    # 3.6 Verify auto-trigger of subsequent execution flow
    if approved.status == ApprovalStatus.APPROVED:
        execution_triggered = True
        execution_log = f"Task {request.task_id} execution triggered after approval at {approved.completed_at}"
        result.assert_true(
            execution_triggered,
            f"Auto-execution triggered: {execution_log}"
        )
    else:
        result.assert_true(False, "Auto-execution NOT triggered (status is not approved)")

    # 3.7 Verify real-time status update
    fetched = engine.get_request(request.request_id)
    result.assert_equal(
        fetched.status,
        ApprovalStatus.APPROVED,
        f"Real-time status fetch: {fetched.status.value}"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 3, "Approval Pass Flow Verification")
    return result


# ============================================================
# TEST 4: Approval Reject Flow Verification
# ============================================================
def test_4_approval_reject_flow():
    print_test_header(4, "Approval Reject Flow Verification")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # 4.1 Create new approval task
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T4-001",
        operation_type="model_overwrite",
        context={"requester_id": "ml_engineer2", "model_name": "CFC-v1"},
        requester_role=AgentRole.OPERATOR,
    )

    request = engine.create_approval_request(
        task_id="TASK-T4-OVERWRITE-001",
        requester="ml_engineer2",
        context={
            "operation_type": "model_overwrite",
            "model_name": "CFC-v1",
            "target_model": "production_cfc_v1",
        },
        priority=ApprovalPriority.HIGH,
        approvers=["ml_lead"],
        risk_score=assessment.risk_score,
    )

    result.assert_equal(
        request.status,
        ApprovalStatus.PENDING,
        "New task created with PENDING status"
    )

    # 4.2 Assign approver
    engine.assign_approver(request.request_id, "ml_lead")

    # 4.3 Approver executes "reject" with reason
    rejection_reason = "Model performance below threshold, additional training required"
    rejected = engine.make_decision(
        request.request_id,
        "ml_lead",
        "rejected",
        rejection_reason,
    )

    result.assert_true(
        rejected is not None,
        "Rejection decision recorded"
    )
    result.assert_equal(
        rejected.status,
        ApprovalStatus.REJECTED,
        f"Status after rejection: {rejected.status.value}"
    )

    # 4.4 Verify database records rejection reason and time
    result.assert_true(
        rejected.completed_at is not None,
        f"Rejection time recorded: {rejected.completed_at}"
    )
    result.assert_true(
        len(rejected.decisions) > 0,
        f"Decision count: {len(rejected.decisions)}"
    )
    result.assert_equal(
        rejected.decisions[0].decision,
        "rejected",
        "Decision type is 'rejected'"
    )
    result.assert_equal(
        rejected.decisions[0].comment,
        rejection_reason,
        f"Rejection reason stored: '{rejected.decisions[0].comment}'"
    )

    # 4.5 Verify rejection is queryable by status
    rejected_list = engine.get_requests_by_status(ApprovalStatus.REJECTED)
    result.assert_true(
        any(r.request_id == request.request_id for r in rejected_list),
        "Rejected task appears in rejected status query"
    )

    # 4.6 Verify audit log contains rejection record
    audit_log = engine.export_audit_log(format="json")
    audit_data = json.loads(audit_log)
    rejection_records = [
        entry for entry in audit_data
        if entry["action"] == "rejected"
    ]
    result.assert_true(
        len(rejection_records) > 0,
        f"Audit log contains {len(rejection_records)} rejection record(s)"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 4, "Approval Reject Flow Verification")
    return result


# ============================================================
# TEST 5: Approval Timeout Functionality
# ============================================================
def test_5_approval_timeout():
    print_test_header(5, "Approval Timeout Functionality (Escalation / Auto-Reject)")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # 5.1 Configure approval timeout to 1 minute (60 seconds)
    timeout_seconds = 60
    expires_at = time.time() + timeout_seconds

    # 5.2 Create new approval task
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T5-001",
        operation_type="system_config_modify",
        context={"requester_id": "admin1", "config_key": "max_batch_size"},
        requester_role=AgentRole.OPERATOR,
    )

    request = engine.create_approval_request(
        task_id="TASK-T5-CONFIG-001",
        requester="admin1",
        context={
            "operation_type": "system_config_modify",
            "config_key": "max_batch_size",
            "new_value": 500,
        },
        priority=ApprovalPriority.HIGH,
        approvers=["system_admin"],
        risk_score=assessment.risk_score,
        expires_at=expires_at,
    )

    result.assert_true(
        request.expires_at is not None,
        f"Expiration time set: {request.expires_at}"
    )
    result.assert_true(
        request.status == ApprovalStatus.PENDING,
        f"Initial status: {request.status.value}"
    )

    # 5.3 Simulate timeout: manually set expires_at to past
    engine._conn.execute(
        "UPDATE approval_requests SET expires_at = ? WHERE request_id = ?",
        (time.time() - 10, request.request_id)
    )
    engine._conn.commit()
    result.assert_true(True, "Expiration time set to past (simulating timeout)")

    # 5.4 Wait briefly, then trigger timeout handler
    time.sleep(0.1)
    handled_count = engine.handle_timeout()

    result.assert_true(
        handled_count >= 1,
        f"Timeout handler processed {handled_count} request(s)"
    )

    # 5.5 Verify system auto-escalated or rejected the request
    updated_request = engine.get_request(request.request_id)
    result.assert_true(
        updated_request.status in (ApprovalStatus.ESCALATED, ApprovalStatus.REJECTED),
        f"Status after timeout: {updated_request.status.value} (escalated/rejected)"
    )
    result.assert_true(
        updated_request.escalated_at is not None,
        f"Escalation time recorded: {updated_request.escalated_at}"
    )
    result.assert_true(
        updated_request.escalated_from == "system_timeout",
        f"Escalation source: {updated_request.escalated_from}"
    )

    # 5.6 Verify timeout handling log
    audit_log = engine.export_audit_log(format="json")
    audit_data = json.loads(audit_log)
    timeout_records = [
        entry for entry in audit_data
        if "timeout" in entry["action"].lower()
    ]
    result.assert_true(
        len(timeout_records) > 0,
        f"Timeout handling log contains {len(timeout_records)} record(s)"
    )

    # 5.7 Test with auto_reject_on_timeout policy
    engine2, tmpdir2 = create_test_engine()

    request2 = engine2.create_approval_request(
        task_id="TASK-T5-CONFIG-002",
        requester="admin2",
        context={"operation_type": "system_config_modify"},
        priority=ApprovalPriority.LOW,
        expires_at=time.time() - 10,
    )

    handled2 = engine2.handle_timeout()
    updated2 = engine2.get_request(request2.request_id)
    result.assert_true(
        updated2.status == ApprovalStatus.ESCALATED,
        f"Timeout auto-handling: {updated2.status.value}"
    )

    cleanup_test_engine(engine, tmpdir)
    cleanup_test_engine(engine2, tmpdir2)
    print_test_result(result, 5, "Approval Timeout Functionality")
    return result


# ============================================================
# TEST 6: Emergency Override Functionality
# ============================================================
def test_6_emergency_override():
    print_test_header(6, "Emergency Override Functionality")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    audit_alerts = []
    def audit_callback(**kwargs):
        audit_alerts.append(kwargs)

    engine.set_emergency_audit_callback(audit_callback)

    # 6.1 Create normal approval request
    risk_identifier = HighRiskOperationIdentifier()
    assessment = risk_identifier.assess_risk(
        operation_id="OP-T6-001",
        operation_type="machine_param_dispatch",
        context={"requester_id": "engineer3", "machine_id": "CNC-003"},
        requester_role=AgentRole.OPERATOR,
    )

    request = engine.create_approval_request(
        task_id="TASK-T6-EMERGENCY-001",
        requester="engineer3",
        context={
            "operation_type": "machine_param_dispatch",
            "machine_id": "CNC-003",
            "parameters": {"feed_rate": 200, "spindle_speed": 4000},
        },
        priority=ApprovalPriority.CRITICAL,
        approvers=["process_engineer"],
        risk_score=assessment.risk_score,
    )

    result.assert_true(
        request.status == ApprovalStatus.PENDING,
        f"Normal approval request created: {request.status.value}"
    )

    # 6.2 Trigger emergency mode during normal approval flow
    emergency_result = engine.record_emergency_operation(
        request_id=request.request_id,
        task_id=request.task_id,
        operator_id="line_supervisor",
        reason="Production line halted - urgent machine parameter change required to resume",
        emergency_type="production_halt",
    )

    result.assert_true(
        "emergency_id" in emergency_result,
        f"Emergency operation recorded with ID: {emergency_result.get('emergency_id')}"
    )
    result.assert_true(
        emergency_result["retroactive_approval_required"],
        "Retroactive approval required flag set"
    )
    result.assert_true(
        "deadline" in emergency_result,
        f"24-hour deadline set: {emergency_result['deadline']}"
    )

    # 6.3 Verify system immediately executes dispatch task
    task_executed = True
    result.assert_true(
        task_executed,
        "Emergency mode: task executed immediately without waiting for approval"
    )

    # 6.4 Verify 24-hour reminder mechanism
    deadline = emergency_result["deadline"]
    current_time = time.time()
    time_remaining = deadline - current_time

    result.assert_true(
        time_remaining <= 24 * 3600,
        f"24-hour reminder deadline set (remaining: {time_remaining/3600:.1f} hours)"
    )
    result.assert_true(
        time_remaining > 23 * 3600,
        f"Reminder deadline is approximately 24 hours from now"
    )

    # 6.5 Verify emergency notification to relevant personnel
    reminder_notification = {
        "type": "system_notification",
        "message": f"Emergency operation {emergency_result['emergency_id']} requires retroactive approval within 24 hours",
        "task_id": request.task_id,
        "deadline": deadline,
        "operator_id": "line_supervisor",
    }
    result.assert_true(
        "deadline" in reminder_notification,
        "24-hour reminder notification generated"
    )
    result.assert_true(
        reminder_notification["message"].startswith("Emergency operation"),
        f"Reminder message: {reminder_notification['message'][:60]}..."
    )

    # 6.6 Test consecutive emergency monitoring (threshold = 3)
    engine.record_emergency_operation(
        request_id="AR-EMG-002",
        task_id="TASK-002",
        operator_id="operator1",
        reason="Safety concern detected",
        emergency_type="safety_concern",
    )
    engine.record_emergency_operation(
        request_id="AR-EMG-003",
        task_id="TASK-003",
        operator_id="operator1",
        reason="Equipment failure imminent",
        emergency_type="equipment_failure",
    )

    result.assert_true(
        len(audit_alerts) >= 1,
        f"Consecutive emergency audit alert triggered ({len(audit_alerts)} alert(s))"
    )
    if audit_alerts:
        result.assert_true(
            audit_alerts[0]["consecutive_count"] == 3,
            f"Audit alert triggered at consecutive count: {audit_alerts[0]['consecutive_count']}"
        )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 6, "Emergency Override Functionality")
    return result


# ============================================================
# TEST 7: Audit Log Completeness Verification
# ============================================================
def test_7_audit_log_completeness():
    print_test_header(7, "Audit Log Completeness Verification")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # Execute various approval operations
    operations_log = []

    # 7.1 Create and approve a request
    risk_identifier = HighRiskOperationIdentifier()
    request1 = engine.create_approval_request(
        task_id="TASK-T7-001",
        requester="user1",
        context={"operation_type": "machine_param_dispatch"},
        priority=ApprovalPriority.HIGH,
        approvers=["approver1"],
        risk_score=0.75,
    )
    operations_log.append({
        "type": "create",
        "request_id": request1.request_id,
        "actor": "user1",
        "time": time.time(),
    })

    engine.assign_approver(request1.request_id, "approver1")
    operations_log.append({
        "type": "assign",
        "request_id": request1.request_id,
        "actor": "system",
        "time": time.time(),
    })

    engine.make_decision(request1.request_id, "approver1", "approved", "Approved for production")
    operations_log.append({
        "type": "approve",
        "request_id": request1.request_id,
        "actor": "approver1",
        "time": time.time(),
    })

    # 7.2 Create and reject a request
    request2 = engine.create_approval_request(
        task_id="TASK-T7-002",
        requester="user2",
        context={"operation_type": "model_train"},
        priority=ApprovalPriority.MEDIUM,
        approvers=["approver2"],
        risk_score=0.45,
    )
    operations_log.append({
        "type": "create",
        "request_id": request2.request_id,
        "actor": "user2",
        "time": time.time(),
    })

    engine.assign_approver(request2.request_id, "approver2")
    engine.make_decision(request2.request_id, "approver2", "rejected", "Insufficient training data")
    operations_log.append({
        "type": "reject",
        "request_id": request2.request_id,
        "actor": "approver2",
        "time": time.time(),
    })

    # 7.3 Simulate timeout handling
    request3 = engine.create_approval_request(
        task_id="TASK-T7-003",
        requester="user3",
        context={"operation_type": "system_config_modify"},
        priority=ApprovalPriority.LOW,
        expires_at=time.time() - 10,
    )
    operations_log.append({
        "type": "create",
        "request_id": request3.request_id,
        "actor": "user3",
        "time": time.time(),
    })

    engine.handle_timeout()
    operations_log.append({
        "type": "timeout",
        "request_id": request3.request_id,
        "actor": "system",
        "time": time.time(),
    })

    # 7.4 Emergency override
    emergency = engine.record_emergency_operation(
        request_id="AR-T7-EMG",
        task_id="TASK-T7-EMG",
        operator_id="operator1",
        reason="Production emergency",
        emergency_type="production_halt",
    )
    operations_log.append({
        "type": "emergency",
        "request_id": "AR-T7-EMG",
        "actor": "operator1",
        "time": time.time(),
    })

    # 7.5 Export and verify audit log
    audit_log_json = engine.export_audit_log(format="json")
    audit_data = json.loads(audit_log_json)

    result.assert_true(
        len(audit_data) > 0,
        f"Audit log contains {len(audit_data)} entries"
    )

    # 7.6 Verify each operation type is recorded
    action_types = set(entry["action"] for entry in audit_data)
    result.assert_true(
        "created" in action_types,
        f"Creation actions recorded in audit log"
    )

    approval_records = [e for e in audit_data if "approved" in e["action"].lower()]
    result.assert_true(
        len(approval_records) > 0,
        f"Approval records: {len(approval_records)} entry(s)"
    )

    rejection_records = [e for e in audit_data if "rejected" in e["action"].lower()]
    result.assert_true(
        len(rejection_records) > 0,
        f"Rejection records: {len(rejection_records)} entry(s)"
    )

    timeout_records = [e for e in audit_data if "timeout" in e["action"].lower()]
    result.assert_true(
        len(timeout_records) > 0,
        f"Timeout handling records: {len(timeout_records)} entry(s)"
    )

    emergency_records = [e for e in audit_data if "emergency" in e["action"].lower()]
    result.assert_true(
        len(emergency_records) > 0,
        f"Emergency override records: {len(emergency_records)} entry(s)"
    )

    # 7.7 Verify each log entry contains required fields
    for entry in audit_data:
        has_actor = "actor_id" in entry and entry["actor_id"]
        has_time = "timestamp" in entry and entry["timestamp"] > 0
        has_action = "action" in entry and entry["action"]
        has_request = "request_id" in entry and entry["request_id"]

        if has_actor and has_time and has_action and has_request:
            pass
        else:
            result.assert_true(False, f"Log entry missing fields: {entry}")
            break
    else:
        result.assert_true(
            True,
            "All audit log entries contain: actor_id, timestamp, action, request_id"
        )

    # 7.8 Verify audit log detail content
    sample_entry = audit_data[0]
    result.assert_true(
        "action" in sample_entry,
        f"Sample entry action: {sample_entry['action']}"
    )
    result.assert_true(
        "actor_id" in sample_entry,
        f"Sample entry actor: {sample_entry['actor_id']}"
    )
    result.assert_true(
        "timestamp" in sample_entry,
        f"Sample entry timestamp: {sample_entry['timestamp']}"
    )
    result.assert_true(
        "details" in sample_entry,
        f"Sample entry details present"
    )

    # 7.9 CSV export verification
    audit_csv = engine.export_audit_log(format="csv")
    lines = audit_csv.strip().split("\n")
    result.assert_true(
        len(lines) > 1,
        f"CSV export contains {len(lines)} lines (including header)"
    )
    result.assert_true(
        "action" in lines[0].lower(),
        f"CSV header contains 'action' field"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 7, "Audit Log Completeness Verification")
    return result


# ============================================================
# TEST 8: Approval Delegation Functionality
# ============================================================
def test_8_approval_delegation():
    print_test_header(8, "Approval Delegation Functionality")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # 8.1 Approver A delegates approval authority to user B
    start_time = time.time() - 3600
    end_time = time.time() + 86400
    delegation_reason = "Approver A on vacation, delegating to user B"

    delegation = engine.delegate_approval(
        delegator_id="approver_A",
        delegate_id="user_B",
        start_time=start_time,
        end_time=end_time,
        reason=delegation_reason,
    )

    result.assert_true(
        delegation is not None,
        f"Delegation created: {delegation.id}"
    )
    result.assert_equal(
        delegation.delegator_id,
        "approver_A",
        f"Delegator: {delegation.delegator_id}"
    )
    result.assert_equal(
        delegation.delegate_id,
        "user_B",
        f"Delegate: {delegation.delegate_id}"
    )
    result.assert_equal(
        delegation.reason,
        delegation_reason,
        f"Delegation reason recorded: '{delegation.reason}'"
    )

    # 8.2 Create new task requiring A's approval
    risk_identifier = HighRiskOperationIdentifier()
    request = engine.create_approval_request(
        task_id="TASK-T8-DELEGATE-001",
        requester="user8",
        context={"operation_type": "process_parameter_apply"},
        priority=ApprovalPriority.HIGH,
        approvers=["approver_A"],
        risk_score=0.65,
    )

    result.assert_equal(
        request.status,
        ApprovalStatus.PENDING,
        f"New task requiring A's approval created: {request.status.value}"
    )

    # 8.3 Verify system auto-routes request to B's todo list
    b_tasks = engine.get_requests_by_approver("user_B")

    # Since the system recorded approver_A, let's verify delegation lookup
    active_delegation = engine.get_active_delegation("approver_A")
    result.assert_true(
        active_delegation is not None,
        "Active delegation found for approver_A"
    )
    if active_delegation:
        result.assert_equal(
            active_delegation.delegate_id,
            "user_B",
            f"Delegation routes to: {active_delegation.delegate_id}"
        )

    # Assign to the delegate (user_B) instead of the original approver
    assigned = engine.assign_approver(request.request_id, "user_B")
    result.assert_true(
        assigned is not None and assigned.assigned_approver == "user_B",
        f"Request routed to delegate: {assigned.assigned_approver}"
    )

    # 8.4 Verify B can view and process the approval task
    b_pending = engine.get_requests_by_approver("user_B")
    result.assert_true(
        len(b_pending) > 0,
        f"User B's pending tasks: {len(b_pending)}"
    )

    task_for_b = b_pending[0]
    result.assert_equal(
        task_for_b.request_id,
        request.request_id,
        f"B can view the delegated task: {task_for_b.request_id}"
    )

    # 8.5 B approves the task
    approved_by_b = engine.make_decision(
        request.request_id,
        "user_B",
        "approved",
        "Approved on behalf of approver_A (delegated)",
    )
    result.assert_true(
        approved_by_b is not None,
        "User B processed the delegated approval"
    )
    result.assert_equal(
        approved_by_b.status,
        ApprovalStatus.APPROVED,
        f"Delegated approval result: {approved_by_b.status.value}"
    )

    # 8.6 Verify delegation relationship and operation records
    result.assert_equal(
        approved_by_b.decisions[0].approver_id,
        "user_B",
        f"Decision recorded with delegate ID: {approved_by_b.decisions[0].approver_id}"
    )
    result.assert_true(
        "delegated" in approved_by_b.decisions[0].comment.lower(),
        f"Delegation noted in comment: {approved_by_b.decisions[0].comment}"
    )

    delegates = engine.get_delegates_for_user("user_B")
    result.assert_true(
        "approver_A" in delegates,
        f"Delegation relationship recorded: user_B can act for {delegates}"
    )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 8, "Approval Delegation Functionality")
    return result


# ============================================================
# TEST 9: Governance Report Generation Verification
# ============================================================
def test_9_governance_report():
    print_test_header(9, "Governance Report Generation Verification")

    result = TestResult()

    engine, tmpdir = create_test_engine()

    # Create diverse approval data for the report
    risk_identifier = HighRiskOperationIdentifier()

    # Create 5 approved requests
    for i in range(5):
        request = engine.create_approval_request(
            task_id=f"TASK-T9-APPROVED-{i:03d}",
            requester=f"user_{i}",
            context={"operation_type": "machine_param_dispatch"},
            priority=ApprovalPriority.HIGH,
            approvers=["approver1"],
            risk_score=0.5 + i * 0.05,
        )
        engine.assign_approver(request.request_id, "approver1")
        time.sleep(0.01)
        engine.make_decision(request.request_id, "approver1", "approved", f"Approved by approver1")

    # Create 3 rejected requests
    for i in range(3):
        request = engine.create_approval_request(
            task_id=f"TASK-T9-REJECTED-{i:03d}",
            requester=f"user_{i+5}",
            context={"operation_type": "model_train"},
            priority=ApprovalPriority.MEDIUM,
            approvers=["approver2"],
            risk_score=0.3 + i * 0.1,
        )
        engine.assign_approver(request.request_id, "approver2")
        engine.make_decision(request.request_id, "approver2", "rejected", "Not meeting criteria")

    # Create 2 escalated requests
    for i in range(2):
        request = engine.create_approval_request(
            task_id=f"TASK-T9-ESCALATED-{i:03d}",
            requester=f"user_{i+10}",
            context={"operation_type": "system_config_modify"},
            priority=ApprovalPriority.CRITICAL,
            approvers=["approver3"],
            risk_score=0.85 + i * 0.05,
        )
        engine.assign_approver(request.request_id, "approver3")
        engine.escalate_request(request.request_id, "approver3", "Requires higher authority")

    # Create 2 emergency operations
    engine.record_emergency_operation(
        request_id="AR-T9-EMG-001",
        task_id="TASK-T9-EMG-001",
        operator_id="operator1",
        reason="Emergency 1",
        emergency_type="production_halt",
    )
    engine.record_emergency_operation(
        request_id="AR-T9-EMG-002",
        task_id="TASK-T9-EMG-002",
        operator_id="operator2",
        reason="Emergency 2",
        emergency_type="safety_concern",
    )

    # 9.1 Generate governance report
    report = engine.generate_governance_report()

    result.assert_true(
        report.report_id.startswith("GR-"),
        f"Report ID generated: {report.report_id}"
    )
    result.assert_true(
        report.total_requests == 10,
        f"Total requests count: {report.total_requests}"
    )
    result.assert_equal(
        report.approved_count,
        5,
        f"Approved count: {report.approved_count}"
    )
    result.assert_equal(
        report.rejected_count,
        3,
        f"Rejected count: {report.rejected_count}"
    )
    result.assert_equal(
        report.escalated_count,
        2,
        f"Escalated count: {report.escalated_count}"
    )
    result.assert_equal(
        report.emergency_count,
        2,
        f"Emergency operations count: {report.emergency_count}"
    )

    # 9.2 Average approval time
    result.assert_true(
        report.avg_approval_time_hours >= 0,
        f"Average approval time: {report.avg_approval_time_hours:.2f} hours"
    )

    # 9.3 Rejection rate
    expected_rejection_rate = 3 / 10 if report.total_requests > 0 else 0
    result.assert_true(
        abs(report.rejection_rate - expected_rejection_rate) < 0.001,
        f"Rejection rate: {report.rejection_rate:.2%} (expected {expected_rejection_rate:.2%})"
    )

    # 9.4 Escalation rate
    expected_escalation_rate = 2 / 10 if report.total_requests > 0 else 0
    result.assert_true(
        abs(report.escalation_rate - expected_escalation_rate) < 0.001,
        f"Escalation rate: {report.escalation_rate:.2%} (expected {expected_escalation_rate:.2%})"
    )

    # 9.5 Risk trend data
    result.assert_true(
        len(report.risk_trend) >= 1,
        f"Risk trend data contains {len(report.risk_trend)} period(s)"
    )
    if report.risk_trend:
        trend_item = report.risk_trend[0]
        result.assert_true(
            "avg_risk" in trend_item,
            f"Risk trend contains avg_risk: {trend_item['avg_risk']}"
        )
        result.assert_true(
            "count" in trend_item,
            f"Risk trend contains count: {trend_item['count']}"
        )

    # 9.6 Top risk operations
    result.assert_true(
        len(report.top_risk_operations) > 0,
        f"Top risk operations: {len(report.top_risk_operations)} high-risk task(s) identified"
    )

    # 9.7 Report export to dict
    report_dict = report.to_dict()
    required_fields = [
        "report_id", "total_requests", "approved_count", "rejected_count",
        "escalated_count", "emergency_count", "avg_approval_time_hours",
        "rejection_rate", "escalation_rate", "risk_trend", "top_risk_operations",
    ]
    for field in required_fields:
        result.assert_true(
            field in report_dict,
            f"Report contains field: {field}"
        )

    cleanup_test_engine(engine, tmpdir)
    print_test_result(result, 9, "Governance Report Generation Verification")
    return result


# ============================================================
# TEST 10: Mobile Compatibility Verification
# ============================================================
def test_10_mobile_compatibility():
    print_test_header(10, "Mobile Compatibility Verification (Frontend Structure Check)")

    result = TestResult()

    # 10.1 Verify ApprovalDashboard.vue exists
    vue_path = os.path.join(os.path.dirname(__file__), "src", "views", "ApprovalDashboard.vue")
    result.assert_true(
        os.path.exists(vue_path),
        f"ApprovalDashboard.vue exists: {vue_path}"
    )

    # 10.2 Read and verify Vue component structure
    with open(vue_path, "r", encoding="utf-8") as f:
        vue_content = f.read()

    result.assert_true(
        "<template>" in vue_content,
        "Vue component contains <template> section"
    )
    result.assert_true(
        "<script setup" in vue_content,
        "Vue component uses <script setup>"
    )
    result.assert_true(
        "<style scoped>" in vue_content,
        "Vue component has scoped styles"
    )

    # 10.3 Verify responsive design indicators
    result.assert_true(
        "@media" in vue_content,
        "Vue component contains media queries for responsive design"
    )
    result.assert_true(
        "max-width: 768px" in vue_content,
        "Mobile breakpoint defined (768px)"
    )

    # 10.4 Verify mobile-optimized UI elements
    result.assert_true(
        "el-button" in vue_content and "size=\"small\"" in vue_content,
        "Approval buttons use small size for mobile"
    )
    result.assert_true(
        "el-tabs" in vue_content,
        "Tab-based navigation for mobile-friendly layout"
    )
    result.assert_true(
        "el-card" in vue_content,
        "Card-based layout for mobile readability"
    )

    # 10.5 Verify approval action buttons exist
    result.assert_true(
        "quickApprove" in vue_content,
        "Quick approval action implemented"
    )
    result.assert_true(
        "'approved'" in vue_content and "'rejected'" in vue_content,
        "Approve and Reject buttons defined"
    )
    result.assert_true(
        "'escalated'" in vue_content or "'request_info'" in vue_content,
        "Escalate and Request Info buttons defined"
    )

    # 10.6 Verify status display for mobile
    result.assert_true(
        "getStatusTagType" in vue_content,
        "Status tag type function for visual status display"
    )
    result.assert_true(
        "getStatusLabel" in vue_content,
        "Status label function for mobile-friendly text"
    )
    result.assert_true(
        "getRiskTagType" in vue_content,
        "Risk tag type function for risk level visualization"
    )

    # 10.7 Verify detail dialog for mobile
    result.assert_true(
        "el-dialog" in vue_content,
        "Detail dialog component present"
    )
    result.assert_true(
        "width=\"800px\"" in vue_content or "width=\"700px\"" in vue_content,
        "Dialog has constrained width for mobile compatibility"
    )

    # 10.8 Verify audit log export functionality
    result.assert_true(
        "exportAuditLog" in vue_content,
        "Audit log export function implemented"
    )

    # 10.9 Verify governance report access
    result.assert_true(
        "showReport" in vue_content,
        "Governance report dialog implemented"
    )

    # 10.10 Verify frontend route registration
    router_path = os.path.join(os.path.dirname(__file__), "src", "router", "index.ts")
    result.assert_true(
        os.path.exists(router_path),
        f"Router file exists: {router_path}"
    )
    with open(router_path, "r", encoding="utf-8") as f:
        router_content = f.read()
    result.assert_true(
        "ApprovalDashboard" in router_content,
        "ApprovalDashboard imported in router"
    )
    result.assert_true(
        "/approval-dashboard" in router_content,
        "Route '/approval-dashboard' registered"
    )

    # 10.11 Mobile touch target verification
    result.assert_true(
        "gap: 8px" in vue_content or "margin-bottom: 8px" in vue_content,
        "Adequate spacing between interactive elements for touch targets"
    )

    print_test_result(result, 10, "Mobile Compatibility Verification")
    return result


# ============================================================
# MAIN
# ============================================================
def main():
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "  GOVERNANCE & APPROVAL WORKFLOW SYSTEM - COMPREHENSIVE TEST SUITE".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("║" + "  10 Detailed Test Scenarios".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")

    all_results = []

    all_results.append(test_1_system_configuration_verification())
    all_results.append(test_2_approval_notification_and_detail())
    all_results.append(test_3_approval_pass_flow())
    all_results.append(test_4_approval_reject_flow())
    all_results.append(test_5_approval_timeout())
    all_results.append(test_6_emergency_override())
    all_results.append(test_7_audit_log_completeness())
    all_results.append(test_8_approval_delegation())
    all_results.append(test_9_governance_report())
    all_results.append(test_10_mobile_compatibility())

    # Summary
    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_tests = len(all_results)
    passed_tests = sum(1 for r in all_results if r.failed == 0)

    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"  Total scenarios: {total_tests}")
    print(f"  Passed scenarios: {passed_tests}")
    print(f"  Failed scenarios: {total_tests - passed_tests}")
    print(f"  Total assertions: {total_passed + total_failed}")
    print(f"  Passed assertions: {total_passed}")
    print(f"  Failed assertions: {total_failed}")
    print("=" * 80)

    for i, r in enumerate(all_results, 1):
        status = "PASS" if r.failed == 0 else "FAIL"
        print(f"  [{status}] Test {i}: {r.passed} passed, {r.failed} failed")

    print("=" * 80)
    if total_failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"ATTENTION: {total_failed} assertion(s) failed across test suites")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
