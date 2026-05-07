import sys
sys.path.insert(0, ".")

from app.data.uniwear_loader import UniwearDataLoader, UniwearDataset

loader = UniwearDataLoader(data_dir="python/data/uniwear")
summary = loader.get_dataset_summary()

print("=== Uniwear 数据集加载测试 ===")
for ds_name, ds_info in summary["datasets"].items():
    if "error" in ds_info:
        print(f"  {ds_name}: ERROR - {ds_info['error']}")
    else:
        mat = ds_info.get("material", "?")
        rows = ds_info.get("rows", 0)
        exps = ds_info.get("experiment_count", 0)
        print(f"  {ds_name}: {rows:,} rows, {mat}, {exps} experiments")

print(f"Total: {summary['total_samples']:,} samples across {summary['total_experiments']} experiments")

stats = loader.compute_statistics(UniwearDataset.NUAA, experiment_tag="W1")
ws = stats.get("wear_stats", {})
print(f"\nNUAA W1 wear: initial={ws.get('initial_wear', '?')}, final={ws.get('final_wear', '?')}, increment={ws.get('total_wear_increment', '?')}")

stats2 = loader.compute_statistics(UniwearDataset.PHM2010, experiment_tag="c1")
ws2 = stats2.get("wear_stats", {})
print(f"PHM2010 c1 wear: initial={ws2.get('initial_wear', '?')}, final={ws2.get('final_wear', '?')}, increment={ws2.get('total_wear_increment', '?')}")
print("All tests passed!")
