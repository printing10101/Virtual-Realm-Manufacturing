"""完全重写所有相关文件以更新 IDE 缓存和文件状态"""
import os
import time

ROOT = r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python"

FILES = [
    r"app\ai\cross_layer_fusion\fusion.py",
    r"app\ai\ijepa_3d\config.py",
    r"app\ai\ijepa_3d\dataset.py",
    r"app\ai\ijepa_3d\geometry_head.py",
    r"app\ai\ijepa_3d\ijepa_encoder.py",
    r"app\ai\ijepa_3d\inference.py",
    r"app\ai\ijepa_3d\losses.py",
    r"app\ai\ijepa_3d\model.py",
    r"app\ai\ijepa_3d\predictor.py",
    r"app\ai\ijepa_3d\resnet_backbone.py",
    r"app\ai\ijepa_3d\trainer.py",
    r"app\ai\ijepa_3d\view_fusion.py",
    r"app\ai\jepa_world_model\config.py",
    r"app\ai\jepa_world_model\predictor.py",
    r"app\ai\jepa_world_model\trainer.py",
    r"app\ai\process_understanding\engine.py",
    r"app\ai\process_understanding\knowledge_retriever.py",
    r"app\ai\process_understanding\prediction_explainer.py",
    r"app\ai\process_understanding\routes.py",
    r"app\ai\unified_embedding\aligner.py",
    r"app\ai\unified_embedding\encoder.py",
    r"app\ai\unified_embedding\interfaces.py",
    r"app\ai\unified_embedding\space.py",
    r"app\ai\vjepa_machining\action_predictor.py",
    r"app\ai\vjepa_machining\alert_module.py",
    r"app\ai\vjepa_machining\anomaly_head.py",
    r"app\ai\vjepa_machining\dataset.py",
    r"app\ai\vjepa_machining\feature_engineering.py",
    r"app\ai\vjepa_machining\inference.py",
    r"app\ai\vjepa_machining\model.py",
    r"app\ai\vjepa_machining\spatiotemporal_vit.py",
    r"app\ai\vjepa_machining\trainer.py",
    r"app\rules\safety_constraint_rules.py",
    r"scripts\infer_ijepa_3d.py",
    r"scripts\infer_vjepa_machining.py",
    r"scripts\train_ijepa_3d.py",
    r"scripts\train_vjepa_machining.py",
    r"tests\ijepa_3d\test_3d_reconstruction_accuracy.py",
    r"tests\ijepa_3d\test_feature_point_detection.py",
    r"tests\ijepa_3d\test_few_shot_learning.py",
    r"tests\ijepa_3d\test_occlusion_robustness.py",
    r"tests\lnn\test_lnn_benchmark.py",
    r"tests\lnn\test_lnn_cross_validation.py",
    r"tests\lnn\test_prediction_distribution.py",
    r"tests\lnn\test_residual_analysis.py",
    r"tests\process_understanding\test_llm_consistency.py",
    r"tests\rules\test_rule_audit_logging.py",
    r"tests\rules\test_rule_boundary_conditions.py",
    r"tests\rules\test_rule_conflict_detection.py",
    r"tests\rules\test_rule_coverage.py",
    r"tests\rules\test_rule_response_time.py",
    r"tests\test_counterfactual_reasoning.py",
    r"tests\test_data_pipeline_integrity.py",
    r"tests\test_multi_step_planning.py",
    r"tests\test_planning_efficiency.py",
    r"tests\test_planning_robustness.py",
    r"tests\test_world_model_single_step.py",
]


def normalize_newlines_and_ensure_trailing(content_bytes: bytes) -> bytes:
    """规范化行尾为 LF，并确保文件末尾有且仅有一个换行符"""
    # 读取内容
    text = content_bytes.decode("utf-8", errors="replace")
    # 移除所有可能的尾部空白行（包括空行）
    # 先确保末尾是换行符
    text = text.rstrip("\r\n")
    # 添加一个 LF 换行符
    return text.encode("utf-8") + b"\n"


fixed_count = 0
for rel_path in FILES:
    full_path = os.path.join(ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[SKIP] 文件不存在: {rel_path}")
        continue

    with open(full_path, "rb") as f:
        original = f.read()

    normalized = normalize_newlines_and_ensure_trailing(original)

    if normalized != original:
        with open(full_path, "wb") as f:
            f.write(normalized)
        # 更新修改时间
        now = time.time()
        os.utime(full_path, (now, now))
        fixed_count += 1
        print(f"[FIXED] {rel_path} ({len(original)} -> {len(normalized)} bytes)")
    else:
        print(f"[OK] {rel_path}")

print(f"\n总计修复 {fixed_count} 个文件")
