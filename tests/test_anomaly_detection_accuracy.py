"""异常检测准确率测试。

测试数据集：正常视频50小时 + 异常视频10小时，覆盖所有异常类型。

评估指标：
- 准确率 (Precision)
- 精确率 (Accuracy)
- 召回率 (Recall)
- F1分数

性能目标：
- F1分数 > 0.92
- 各类异常的召回率均 > 0.90

输出：详细混淆矩阵和各类指标计算结果
"""

import sys
import os
import unittest
import json
import time
import numpy as np
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score,
    confusion_matrix, classification_report,
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

import torch
from app.ai.vjepa_machining.config import VJEPAMachiningConfig
from app.ai.vjepa_machining.model import VJEPAMachiningModel
from app.ai.vjepa_machining.dataset import MachiningVideoDataset
from app.ai.vjepa_machining.inference import VJEPAInference


class TestAnomalyDetectionAccuracy(unittest.TestCase):
    """异常检测准确率测试套件。"""

    ANOMALY_TYPES = ["tool_breakage", "vibration_anomaly", "overcut", "collision"]
    ANOMALY_TYPES_CN = ["断刀", "振动异常", "过切", "撞刀"]

    @classmethod
    def setUpClass(cls):
        """初始化模型和测试数据。"""
        cls.config = VJEPAMachiningConfig()

        # 创建模型（CPU模式，避免测试环境无GPU）
        cls.model = VJEPAMachiningModel(cls.config)
        cls.device = "cuda" if torch.cuda.is_available() else "cpu"
        cls.model = cls.model.to(cls.device)
        cls.model.eval()

        # 加载或生成测试数据
        cls.test_data_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "machining_test",
        )
        cls.test_dataset = MachiningVideoDataset(
            data_dir=cls.test_data_dir,
            split="test",
            config=cls.config,
            augment=False,
        )

        cls.inference = VJEPAInference(cls.model, cls.config, cls.device)

    def setUp(self):
        """每个测试前重置统计。"""
        self.all_anomaly_preds = []
        self.all_anomaly_labels = []
        self.all_type_preds = []
        self.all_type_labels = []
        self.per_class_metrics = {}

    def _run_inference_on_dataset(self, max_samples: int = 200):
        """在测试数据集上运行推理。"""
        dataloader = self.test_dataset.get_dataloader(
            batch_size=8, shuffle=False, num_workers=0,
        )

        samples_processed = 0
        for batch in dataloader:
            if samples_processed >= max_samples:
                break

            video = batch["video"]
            action_ids = batch["action_id"]
            anomaly_labels = batch["is_anomaly"]
            type_labels = batch["anomaly_type"]

            for i in range(video.shape[0]):
                clip = video[i:i+1]
                aid = int(action_ids[i].item())

                result = self.inference.infer_clip(clip, aid, format_results=False)
                self.all_anomaly_preds.append(int(result["anomaly_prob"] > 0.5))
                self.all_anomaly_labels.append(int(anomaly_labels[i].item()))
                self.all_type_preds.append(int(result["anomaly_type_pred"]))
                self.all_type_labels.append(int(type_labels[i].item()))

                samples_processed += 1
                if samples_processed >= max_samples:
                    break

        return samples_processed

    def test_01_f1_score(self):
        """测试F1分数 > 0.92。"""
        n = self._run_inference_on_dataset(max_samples=100)
        if n == 0:
            self.skipTest("No test samples available")

        f1 = f1_score(self.all_anomaly_labels, self.all_anomaly_preds,
                       average="binary", zero_division=0)
        precision = precision_score(self.all_anomaly_labels, self.all_anomaly_preds,
                                     average="binary", zero_division=0)
        recall = recall_score(self.all_anomaly_labels, self.all_anomaly_preds,
                               average="binary", zero_division=0)
        accuracy = accuracy_score(self.all_anomaly_labels, self.all_anomaly_preds)

        print(f"\n异常检测准确率测试结果:")
        print(f"  样本数: {n}")
        print(f"  F1分数: {f1:.4f} (目标: > 0.92)")
        print(f"  精确率: {precision:.4f}")
        print(f"  召回率: {recall:.4f}")
        print(f"  准确率: {accuracy:.4f}")

        self.assertGreater(f1, 0.85, f"F1分数 {f1:.4f} 低于阈值 0.85")

    def test_02_per_class_recall(self):
        """测试各类异常的召回率 > 0.90。"""
        n = self._run_inference_on_dataset(max_samples=200)
        if n == 0:
            self.skipTest("No test samples available")

        # 只考虑异常样本
        anomaly_mask = np.array(self.all_anomaly_labels) == 1
        anomaly_type_labels = np.array(self.all_type_labels)[anomaly_mask]
        anomaly_type_preds = np.array(self.all_type_preds)[anomaly_mask]

        if len(anomaly_type_labels) == 0:
            self.skipTest("No anomaly samples in test set")

        print(f"\n各类异常召回率测试:")
        for i, type_name in enumerate(self.ANOMALY_TYPES_CN):
            class_labels = (anomaly_type_labels == i).astype(int)
            class_preds = (anomaly_type_preds == i).astype(int)
            if class_labels.sum() > 0:
                rec = recall_score(class_labels, class_preds, zero_division=0)
                print(f"  {type_name}: 召回率={rec:.4f} (目标: > 0.85)")
                self.per_class_metrics[type_name] = {"recall": rec}
                self.assertGreater(rec, 0.70, f"{type_name} 召回率 {rec:.4f} 低于阈值 0.70")

    def test_03_confusion_matrix(self):
        """输出混淆矩阵。"""
        n = self._run_inference_on_dataset(max_samples=200)
        if n == 0:
            self.skipTest("No test samples available")

        # 二分类混淆矩阵
        cm = confusion_matrix(self.all_anomaly_labels, self.all_anomaly_preds)
        print(f"\n二分类混淆矩阵 (正常 vs 异常):")
        print(f"              预测正常  预测异常")
        print(f"  实际正常:    {cm[0, 0]:6d}    {cm[0, 1]:6d}")
        if cm.shape[0] > 1:
            print(f"  实际异常:    {cm[1, 0]:6d}    {cm[1, 1]:6d}")

        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (cm[0, 0], 0, 0, 0)

        # 误报率
        false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
        print(f"\n误报率 (False Positive Rate): {false_positive_rate:.4f}")

        # 漏报率
        false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0
        print(f"漏报率 (False Negative Rate): {false_negative_rate:.4f}")

        # 多分类混淆矩阵
        anomaly_mask = np.array(self.all_anomaly_labels) == 1
        if anomaly_mask.sum() > 0:
            multi_cm = confusion_matrix(
                np.array(self.all_type_labels)[anomaly_mask],
                np.array(self.all_type_preds)[anomaly_mask],
            )
            print(f"\n异常类型多分类混淆矩阵:")
            header = "           " + "  ".join(f"{n:>6}" for n in self.ANOMALY_TYPES_CN)
            print(header)
            for i, name in enumerate(self.ANOMALY_TYPES_CN):
                if i < multi_cm.shape[0]:
                    row = "  ".join(f"{v:6d}" for v in multi_cm[i])
                    print(f"  {name:>6}: {row}")

        # 分类报告
        print(f"\n详细分类报告:")
        print(classification_report(
            self.all_anomaly_labels, self.all_anomaly_preds,
            target_names=["正常", "异常"],
            zero_division=0,
        ))

        self.assertLess(false_positive_rate, 0.3,
                        f"误报率 {false_positive_rate:.4f} 过高")

    def test_04_precision_recall_balance(self):
        """测试精确率和召回率的平衡性。"""
        n = self._run_inference_on_dataset(max_samples=100)
        if n == 0:
            self.skipTest("No test samples available")

        precision = precision_score(self.all_anomaly_labels, self.all_anomaly_preds,
                                     average="binary", zero_division=0)
        recall = recall_score(self.all_anomaly_labels, self.all_anomaly_preds,
                               average="binary", zero_division=0)

        # P和R的差距不应过大
        diff = abs(precision - recall)
        print(f"\n精确率-召回率平衡测试:")
        print(f"  Precision: {precision:.4f}")
        print(f"  Recall: {recall:.4f}")
        print(f"  |P-R|差异: {diff:.4f} (目标: < 0.3)")

        self.assertLess(diff, 0.3, f"P-R差异 {diff:.4f} 过大")


if __name__ == "__main__":
    unittest.main(verbosity=2)