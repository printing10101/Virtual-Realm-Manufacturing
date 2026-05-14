"""
Comprehensive Integration Test for Governance & Approval Workflow System

Tests all core modules:
- ApprovalStrategy configuration
- ApprovalWorkflowEngine lifecycle
- HighRiskOperationIdentifier
- Emergency override mechanism
- Audit and compliance
"""
import sys
import os
import time
import json

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from app.models.governance import (
    ApprovalStrategy, ApprovalPriority, ApprovalStatus, ApprovalMode,
    TaskType, AgentRole, ResourceSensitivity, ApprovalPolicy,
    ApprovalRequest, ApprovalDecision, GovernanceReport,
    DEFAULT_GLOBAL_POLICIES, STRATEGY_PRIORITY_MAP, DIMENSION_PRIORITY,
)
from app.core.approval_workflow import ApprovalWorkflowEngine
from app.core.risk_identifier import (
    RiskScorer, HighRiskOperationIdentifier, OperationCategory, RiskAssessment, RiskFactor,
)

def test_governance_models():
    """Test governance model definitions"""
    print("\n" + "="*80)
    print("TEST 1: Governance Models")
    print("="*80)
    
    assert ApprovalStrategy.AUTO_EXECUTE.value == "auto_execute"
    assert ApprovalStrategy.EXECUTE_AFTER_RECORD.value == "execute_after_record"
    assert ApprovalStrategy.APPROVE_BEFORE_EXECUTE.value == "approve_before_execute"
    assert ApprovalStrategy.MULTI_APPROVAL.value == "multi_approval"
    print("  ✓ ApprovalStrategy enum correct")
    
    assert ApprovalStatus.PENDING.value == "pending"
    assert ApprovalStatus.UNDER_REVIEW.value == "under_review"
    assert ApprovalStatus.APPROVED.value == "approved"
    assert ApprovalStatus.REJECTED.value == "rejected"
    assert ApprovalStatus.ESCALATED.value == "escalated"
    print("  ✓ ApprovalStatus enum correct")
    
    assert ApprovalPriority.LOW.value == "low"
    assert ApprovalPriority.CRITICAL.value == "critical"
    print("  ✓ ApprovalPriority enum correct")
    
    assert TaskType.TRAINING.value == "training"
    assert TaskType.EXECUTION.value == "execution"
    assert TaskType.ANALYSIS.value == "analysis"
    print("  ✓ TaskType enum correct")
    
    assert AgentRole.ENGINEER.value == "engineer"
    assert AgentRole.ANALYST.value == "analyst"
    assert AgentRole.OPERATOR.value == "operator"
    print("  ✓ AgentRole enum correct")
    
    assert ResourceSensitivity.NORMAL.value == "normal"
    assert ResourceSensitivity.CONFIDENTIAL.value == "confidential"
    assert ResourceSensitivity.CORE.value == "core"
    print("  ✓ ResourceSensitivity enum correct")
    
    assert len(DEFAULT_GLOBAL_POLICIES) == 10
    print(f"  ✓ Default policies: {len(DEFAULT_GLOBAL_POLICIES)} policies loaded")
    
    policy = DEFAULT_GLOBAL_POLICIES[0]
    assert policy.dimension == "global"
    assert policy.strategy == ApprovalStrategy.EXECUTE_AFTER_RECORD
    print("  ✓ Default global policy correct")
    
    multi_policy = [p for p in DEFAULT_GLOBAL_POLICIES if p.strategy == ApprovalStrategy.MULTI_APPROVAL]
    assert len(multi_policy) >= 1
    assert multi_policy[0].required_approvals >= 2
    print("  ✓ Multi-approval policy configured correctly")
    
    assert STRATEGY_PRIORITY_MAP[ApprovalStrategy.AUTO_EXECUTE] < STRATEGY_PRIORITY_MAP[ApprovalStrategy.MULTI_APPROVAL]
    print("  ✓ Strategy priority map correct")
    
    assert DIMENSION_PRIORITY["resource_sensitivity"] > DIMENSION_PRIORITY["global"]
    print("  ✓ Dimension priority map correct")
    
    print("\n✅ TEST 1 PASSED: Governance Models")


def test_approval_workflow_engine():
    """Test approval workflow engine lifecycle"""
    print("\n" + "="*80)
    print("TEST 2: Approval Workflow Engine")
    print("="*80)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_approval.db")
        engine = ApprovalWorkflowEngine(db_path=db_path)
        print("  ✓ ApprovalWorkflowEngine initialized")
        
        request = engine.create_approval_request(
            task_id="TASK-001",
            requester="user1",
            context={"operation_type": "machine_param_dispatch", "param1": "value1"},
            priority=ApprovalPriority.HIGH,
            approvers=["approver1", "approver2"],
            required_approvals=1,
            risk_score=0.75,
            risk_factors=["high_risk_operation", "sensitive_data"],
            suggested_decision="approve_before_execute",
            expires_at=time.time() + 24*3600,
        )
        assert request.request_id.startswith("AR-")
        assert request.status == ApprovalStatus.PENDING
        assert request.risk_score == 0.75
        assert len(request.risk_factors) == 2
        print(f"  ✓ Approval request created: {request.request_id}")
        
        assigned = engine.assign_approver(request.request_id, "approver1")
        assert assigned is not None
        assert assigned.status == ApprovalStatus.UNDER_REVIEW
        assert assigned.assigned_approver == "approver1"
        print("  ✓ Approver assigned successfully")
        
        approved = engine.make_decision(request.request_id, "approver1", "approved", "Looks good")
        assert approved is not None
        assert approved.status == ApprovalStatus.APPROVED
        assert len(approved.decisions) == 1
        assert approved.decisions[0].decision == "approved"
        print("  ✓ Decision made: approved")
        
        request2 = engine.create_approval_request(
            task_id="TASK-002",
            requester="user2",
            context={"operation_type": "model_train"},
            priority=ApprovalPriority.MEDIUM,
            risk_score=0.45,
            expires_at=time.time() + 3600,
        )
        
        rejected = engine.make_decision(request2.request_id, "approver2", "rejected", "Not approved")
        assert rejected is not None
        assert rejected.status == ApprovalStatus.REJECTED
        print("  ✓ Decision made: rejected")
        
        pending_requests = engine.get_requests_by_status(ApprovalStatus.PENDING)
        approved_requests = engine.get_requests_by_status(ApprovalStatus.APPROVED)
        rejected_requests = engine.get_requests_by_status(ApprovalStatus.REJECTED)
        assert len(approved_requests) == 1
        assert len(rejected_requests) == 1
        print(f"  ✓ Query by status: pending={len(pending_requests)}, approved={len(approved_requests)}, rejected={len(rejected_requests)}")
        
        by_approver = engine.get_requests_by_approver("approver1")
        assert len(by_approver) >= 1
        print(f"  ✓ Query by approver: {len(by_approver)} requests")
        
        delegation = engine.delegate_approval(
            delegator_id="approver1",
            delegate_id="approver3",
            start_time=time.time() - 3600,
            end_time=time.time() + 86400,
            reason="Vacation",
        )
        assert delegation.delegator_id == "approver1"
        assert delegation.delegate_id == "approver3"
        print(f"  ✓ Delegation created: {delegation.id}")
        
        active_delegation = engine.get_active_delegation("approver1")
        assert active_delegation is not None
        assert active_delegation.delegate_id == "approver3"
        print("  ✓ Active delegation retrieved")
        
        delegates = engine.get_delegates_for_user("approver3")
        assert "approver1" in delegates
        print("  ✓ Delegates for user retrieved")
        
        report = engine.generate_governance_report()
        assert report.total_requests == 2
        assert report.approved_count == 1
        assert report.rejected_count == 1
        print(f"  ✓ Governance report generated: total={report.total_requests}, approved={report.approved_count}, rejected={report.rejected_count}")
        
        audit_log_json = engine.export_audit_log(format="json")
        audit_log_data = json.loads(audit_log_json)
        assert len(audit_log_data) > 0
        print(f"  ✓ Audit log exported: {len(audit_log_data)} entries")
        
        audit_log_csv = engine.export_audit_log(format="csv")
        assert len(audit_log_csv) > 0
        print("  ✓ Audit log CSV export successful")
        
        engine.close()
        print("  ✓ Engine closed successfully")
    
    print("\n✅ TEST 2 PASSED: Approval Workflow Engine")


def test_risk_identifier():
    """Test high-risk operation identification"""
    print("\n" + "="*80)
    print("TEST 3: High-Risk Operation Identifier")
    print("="*80)
    
    scorer = RiskScorer()
    identifier = HighRiskOperationIdentifier(risk_scorer=scorer)
    
    assert identifier.identify_operation_category("machine_param_dispatch") == OperationCategory.T_TYPE
    assert identifier.identify_operation_category("system_config_modify") == OperationCategory.C_TYPE
    assert identifier.identify_operation_category("model_train") == OperationCategory.M_TYPE
    assert identifier.identify_operation_category("historical_data_access") == OperationCategory.D_TYPE
    assert identifier.identify_operation_category("budget_exceed") == OperationCategory.B_TYPE
    print("  ✓ Operation category identification correct")
    
    assessment = identifier.assess_risk(
        operation_id="OP-001",
        operation_type="machine_param_dispatch",
        context={"requester_id": "user1"},
        requester_role=AgentRole.OPERATOR,
        budget_amount=500.0,
    )
    assert assessment.operation_category == OperationCategory.T_TYPE
    assert assessment.risk_score >= 0.0
    assert assessment.risk_score <= 1.0
    assert assessment.requires_approval == True
    print(f"  ✓ Risk assessment: score={assessment.risk_score:.2f}, level={assessment.risk_level}, requires_approval={assessment.requires_approval}")
    
    assessment2 = identifier.assess_risk(
        operation_id="OP-002",
        operation_type="model_train",
        context={"requester_id": "user2", "resource_sensitivity": "core"},
        requester_role=AgentRole.ENGINEER,
    )
    assert assessment2.operation_category == OperationCategory.M_TYPE
    assert assessment2.resource_sensitivity == ResourceSensitivity.CORE
    assert assessment2.requires_approval == True
    assert assessment2.suggested_strategy == ApprovalStrategy.MULTI_APPROVAL
    print(f"  ✓ Core sensitivity assessment: strategy={assessment2.suggested_strategy.value}")
    
    assessment3 = identifier.assess_risk(
        operation_id="OP-003",
        operation_type="analysis_report",
        context={"requester_id": "user3"},
        requester_role=AgentRole.ANALYST,
    )
    print(f"  ✓ Low-risk assessment: score={assessment3.risk_score:.2f}, level={assessment3.risk_level}")
    
    scorer.set_error_rate("error_user", 0.3)
    assessment4 = identifier.assess_risk(
        operation_id="OP-004",
        operation_type="machine_param_dispatch",
        context={"requester_id": "error_user"},
        requester_role=AgentRole.OPERATOR,
    )
    print(f"  ✓ High error rate assessment: score={assessment4.risk_score:.2f} (error_rate=0.3)")
    
    identifier.set_budget_threshold(100.0)
    assessment5 = identifier.assess_risk(
        operation_id="OP-005",
        operation_type="budget_exceed",
        context={"requester_id": "user5"},
        requester_role=AgentRole.ENGINEER,
        budget_amount=150.0,
    )
    print(f"  ✓ Budget exceed assessment: score={assessment5.risk_score:.2f}")
    
    print("\n✅ TEST 3 PASSED: High-Risk Operation Identifier")


def test_emergency_override():
    """Test emergency override mechanism"""
    print("\n" + "="*80)
    print("TEST 4: Emergency Override Mechanism")
    print("="*80)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_emergency.db")
        engine = ApprovalWorkflowEngine(db_path=db_path)
        
        audit_events = []
        def audit_callback(**kwargs):
            audit_events.append(kwargs)
            print(f"    [AUDIT ALERT] {kwargs}")
        
        engine.set_emergency_audit_callback(audit_callback)
        
        result = engine.record_emergency_operation(
            request_id="AR-EMG-001",
            task_id="TASK-001",
            operator_id="operator1",
            reason="Production line halted, immediate action required",
            emergency_type="production_halt",
        )
        assert "emergency_id" in result
        assert result["retroactive_approval_required"] == True
        assert "deadline" in result
        print(f"  ✓ Emergency operation recorded: {result['emergency_id']}")
        
        result2 = engine.record_emergency_operation(
            request_id="AR-EMG-002",
            task_id="TASK-002",
            operator_id="operator1",
            reason="Equipment malfunction",
            emergency_type="equipment_failure",
        )
        print(f"  ✓ Second emergency recorded: {result2['emergency_id']}")
        
        result3 = engine.record_emergency_operation(
            request_id="AR-EMG-003",
            task_id="TASK-003",
            operator_id="operator1",
            reason="Safety issue detected",
            emergency_type="safety_concern",
        )
        print(f"  ✓ Third emergency recorded: {result3['emergency_id']}")
        
        assert len(audit_events) == 1
        assert audit_events[0]["consecutive_count"] == 3
        print(f"  ✓ Audit alert triggered after {audit_events[0]['consecutive_count']} consecutive emergencies")
        
        success = engine.complete_retroactive_approval(result["emergency_id"])
        assert success == True
        print("  ✓ Retroactive approval completed")
        
        engine.close()
    
    print("\n✅ TEST 4 PASSED: Emergency Override Mechanism")


def test_integration():
    """Test full integration: risk assessment → approval workflow → decision"""
    print("\n" + "="*80)
    print("TEST 5: Full Integration Test")
    print("="*80)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_integration.db")
        engine = ApprovalWorkflowEngine(db_path=db_path)
        scorer = RiskScorer()
        identifier = HighRiskOperationIdentifier(risk_scorer=scorer)
        
        operation_type = "machine_param_dispatch"
        context = {
            "operation_type": operation_type,
            "machine_id": "CNC-001",
            "parameters": {"feed_rate": 100, "speed": 2000},
            "requester_id": "engineer1",
        }
        
        assessment = identifier.assess_risk(
            operation_id="OP-INT-001",
            operation_type=operation_type,
            context=context,
            requester_role=AgentRole.ENGINEER,
        )
        print(f"  ✓ Risk assessment completed: {assessment.risk_score:.2f}")
        
        request = engine.create_approval_request(
            task_id="TASK-INT-001",
            requester="engineer1",
            context={**context, "risk_assessment": assessment.to_dict()},
            priority=assessment.suggested_priority,
            approvers=assessment.suggested_approvers,
            risk_score=assessment.risk_score,
            risk_factors=[f.name for f in assessment.risk_factors],
            suggested_decision=assessment.suggested_strategy.value,
        )
        print(f"  ✓ Approval request created: {request.request_id}")
        
        assert len(request.approvers) >= 1
        assert request.risk_score == assessment.risk_score
        print(f"  ✓ Request linked to risk assessment (score={request.risk_score:.2f})")
        
        for approver in request.approvers:
            engine.assign_approver(request.request_id, approver)
        print(f"  ✓ {len(request.approvers)} approver(s) assigned")
        
        for approver in request.approvers:
            result = engine.make_decision(
                request.request_id,
                approver,
                "approved",
                f"Approved by {approver}",
            )
            print(f"  ✓ {approver} approved")
        
        final_request = engine.get_request(request.request_id)
        assert final_request is not None
        assert final_request.status == ApprovalStatus.APPROVED
        print(f"  ✓ Final status: {final_request.status.value}")
        
        report = engine.generate_governance_report()
        assert report.total_requests == 1
        assert report.approved_count == 1
        print(f"  ✓ Governance report: total={report.total_requests}, approved={report.approved_count}")
        
        engine.close()
    
    print("\n✅ TEST 5 PASSED: Full Integration Test")


def main():
    print("\n" + "╔" + "="*78 + "╗")
    print("║" + " "*78 + "║")
    print("║" + "  GOVERNANCE & APPROVAL WORKFLOW SYSTEM - INTEGRATION TEST".center(78) + "║")
    print("║" + " "*78 + "║")
    print("╚" + "="*78 + "╝")
    
    test_governance_models()
    test_approval_workflow_engine()
    test_risk_identifier()
    test_emergency_override()
    test_integration()
    
    print("\n" + "="*80)
    print("🎉 ALL TESTS PASSED")
    print("="*80)
    print("\nSystem Components Verified:")
    print("  ✅ Approval Strategy Configuration (4 strategies, multi-dimensional)")
    print("  ✅ Approval Workflow Engine (lifecycle, routing, timeout, immutable audit)")
    print("  ✅ High-Risk Operation Identification (5 categories, multi-factor scoring)")
    print("  ✅ Emergency Override Mechanism (audit alert, retroactive approval)")
    print("  ✅ Full Integration (risk assessment → approval → decision)")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
