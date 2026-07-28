"""从 run_3datasets.log 提取实验结果并保存为 JSON。

主实验进程在 PHM2010 启动时崩溃（疑似内存累积），但 Synthetic 和 Industrial
两个数据集的 9 模型结果已完整写入日志。本脚本解析日志并重建 JSON 结果文件。
"""
import json
import re
from pathlib import Path

LOG_PATH = Path(__file__).parent / "results" / "run_3datasets.log"
OUTPUT_PATH = Path(__file__).parent / "results" / "all_experiments_results.json"

# 结果模式：匹配 "  mae: 0.3222" 等
METRIC_PATTERN = re.compile(r"^\s+(mae|rmse|r2|mape|pcc):\s+([\d.eE+-]+)$")
MODEL_HEADER_PATTERN = re.compile(r"^训练模型:\s*(.+)$")
EVAL_HEADER_PATTERN = re.compile(r"^(.+?)\s*评估结果:\s*$")
DATASET_HEADER_PATTERN = re.compile(r"^数据集:\s*(.+)$")


def parse_log(log_path: Path) -> dict:
    """解析日志，提取各数据集各模型的评估指标。"""
    results = {}
    current_dataset = None
    current_model = None
    current_metrics = {}
    pending_model = None  # "训练模型:" 行指向的模型

    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")

            # 数据集头
            m = DATASET_HEADER_PATTERN.match(line)
            if m:
                current_dataset = m.group(1).strip()
                results.setdefault(current_dataset, {})
                continue

            # "训练模型: XXX" 行（预告下一个要训练的模型）
            m = MODEL_HEADER_PATTERN.match(line)
            if m:
                pending_model = m.group(1).strip()
                continue

            # "XXX 评估结果:" 行
            m = EVAL_HEADER_PATTERN.match(line)
            if m:
                model_name = m.group(1).strip()
                # 优先使用 pending_model（更准确），否则用评估头里的名字
                current_model = pending_model if pending_model else model_name
                current_metrics = {}
                continue

            # 指标行
            m = METRIC_PATTERN.match(line)
            if m and current_model and current_dataset:
                key = m.group(1)
                value = float(m.group(2))
                current_metrics[key] = value
                # mae 是最后一个指标（mae/rmse/r2/mape 或 mae/rmse/r2/mape/pcc）
                if key == "mape":
                    results[current_dataset][current_model] = dict(current_metrics)
                    current_model = None
                    pending_model = None
                    current_metrics = {}

    return results


def main():
    results = parse_log(LOG_PATH)
    print(f"解析完成，共 {len(results)} 个数据集：")
    for ds_name, models in results.items():
        print(f"  {ds_name}: {len(models)} 个模型")
        for model_name, metrics in models.items():
            mae = metrics.get("mae", "N/A")
            r2 = metrics.get("r2", "N/A")
            pcc = metrics.get("pcc", "N/A")
            print(f"    {model_name:<15} MAE={mae:.4f}  R²={r2:.4f}  PCC={pcc}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] 结果已保存至: {OUTPUT_PATH}")

    # 生成 DL-LNN vs 基线对比摘要
    print("\n" + "=" * 70)
    print("DL-LNN vs 基线对比摘要")
    print("=" * 70)
    for ds_name, models in results.items():
        if "DL-LNN" not in models:
            continue
        dl_lnn = models["DL-LNN"]
        print(f"\n[{ds_name}]")
        print(f"{'Model':<15} {'MAE':<10} {'RMSE':<10} {'R²':<10} {'MAPE':<10} {'PCC':<10}")
        print("-" * 65)
        # 按 MAE 排序
        sorted_models = sorted(models.items(), key=lambda x: x[1].get("mae", 1e9))
        for model_name, metrics in sorted_models:
            mae = metrics.get("mae", 0)
            rmse = metrics.get("rmse", 0)
            r2 = metrics.get("r2", 0)
            mape = metrics.get("mape", 0)
            pcc = metrics.get("pcc", 0)
            marker = " ★" if model_name == "DL-LNN" else ""
            print(f"{model_name:<15} {mae:<10.4f} {rmse:<10.4f} {r2:<10.4f} {mape:<10.4f} {pcc:<10.4f}{marker}")

        # DL-LNN 排名
        dl_lnn_mae = dl_lnn.get("mae", 1e9)
        rank = sum(1 for m in models.values() if m.get("mae", 1e9) < dl_lnn_mae) + 1
        print(f"  → DL-LNN MAE 排名: {rank}/{len(models)}")


if __name__ == "__main__":
    main()
