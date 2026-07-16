"""显示三数据集全部模型结果对比表。"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "results", "all_experiments_results.json")

with open(PATH, "r", encoding="utf-8") as f:
    d = json.load(f)

for ds_name in ["Synthetic", "Industrial", "PHM2010"]:
    if ds_name not in d:
        print(f"\n{ds_name}: 缺失")
        continue
    print("=" * 75)
    print(f"{ds_name} 全部 {len(d[ds_name])} 模型结果（按 MAE 升序）:")
    print("=" * 75)
    rows = sorted(d[ds_name].items(), key=lambda kv: kv[1].get("mae", 999))
    print(f"{'模型':<15} {'MAE':<10} {'RMSE':<10} {'R2':<10} {'MAPE':<10}")
    print("-" * 75)
    for name, m in rows:
        print(f"{name:<15} {m.get('mae',0):<10.4f} {m.get('rmse',0):<10.4f} "
              f"{m.get('r2',0):<10.4f} {m.get('mape',0):<10.4f}")
    dlnn_rank = [n for n, _ in rows].index("DL-LNN") + 1
    print(f"\nDL-LNN MAE 排名: {dlnn_rank}/{len(rows)}")
    print()
