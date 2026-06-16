import json
data = json.load(open("coverage-reports/coverage.json"))
files = data.get("files", {})
for k, v in files.items():
    if "lnn_uncertain" in k and "test" not in k:
        print(f"File: {k}")
        missing = v.get("missing_lines", [])
        executed = v.get("executed_lines", [])
        print(f"  Executed: {executed}")
        print(f"  Missing: {missing}")
