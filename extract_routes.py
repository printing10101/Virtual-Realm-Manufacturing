import os, re

ROOT = r"C:/Users/Lenovo/Desktop/灵境制造（上线版）/engineering/python/app"

routes = []
prefix_for_file = {}

for dirpath,_,files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"): continue
        fp = os.path.join(dirpath, fn)
        try:
            src = open(fp, encoding="utf-8").read()
        except Exception:
            continue
        for m in re.finditer(r'APIRouter\(\s*prefix\s*=\s*"([^"]+)"', src):
            prefix_for_file[fp] = m.group(1)

for dirpath,_,files in os.walk(ROOT):
    for fn in files:
        if not fn.endswith(".py"): continue
        fp = os.path.join(dirpath, fn)
        try:
            lines = open(fp, encoding="utf-8").readlines()
        except Exception:
            continue
        prefix = prefix_for_file.get(fp, "")
        for i in range(len(lines)):
            line = lines[i]
            m = re.match(r'\s*@(\w+)\.(get|post|put|delete|patch|websocket|options)\(', line)
            if not m:
                continue
            obj, meth = m.group(1), m.group(2)
            rest = line[m.end():]
            path = None
            if '"' in rest:
                pm = re.search(r'"([^"]*)"', rest)
                if pm: path = pm.group(1)
            else:
                for j in range(i+1, min(i+4, len(lines))):
                    pm = re.search(r'"([^"]*)"', lines[j])
                    if pm:
                        path = pm.group(1); break
            if path is None:
                path = "<dynamic>"
            if obj in ("app","simple_health_router"):
                full = path
            else:
                full = (prefix.rstrip("/") + "/" + path.lstrip("/")) if path != "<dynamic>" else prefix+"/<dynamic>"
            routes.append((meth.upper(), full, fp.replace(ROOT,""), i+1))

seen=set(); out=[]
for r in routes:
    key=(r[0],r[1])
    if key in seen: continue
    seen.add(key); out.append(r)

out.sort(key=lambda x:(x[1], x[0]))
print("TOTAL_ROUTES", len(out))
for meth,full,rel,ln in out:
    print(f"{meth:7} {full:60} {rel}:{ln}")
