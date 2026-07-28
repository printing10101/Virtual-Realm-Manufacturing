import ast, os, re

API_ROOT = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\python\app"

BUILTIN_TYPES = {
    "Request", "Response", "WebSocket", "BackgroundTasks", "HTTPException",
    "str", "int", "float", "bool", "bytes", "list", "dict", "tuple", "set",
    "None", "Any", "Optional", "Union", "List", "Dict", "Tuple", "Sequence",
    "Callable", "Path", "UploadFile", "Form", "File", "Query", "Header",
    "Depends", "Body", "Cookie", "Annotated", "type", "object", "Exception",
}

def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()

def has_future_import(tree):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(a.name == "annotations" for a in node.names):
                return True
    return False

def is_limiter_decorator(dec):
    f = dec.func if isinstance(dec, ast.Call) else dec
    return isinstance(f, ast.Attribute) and f.attr == "limit" \
        and isinstance(f.value, ast.Name) and f.value.id == "limiter"

def annotation_tokens(ann):
    toks = set()
    if ann is None:
        return toks
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        toks |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", ann.value))
    elif isinstance(ann, ast.Name):
        toks.add(ann.id)
    elif isinstance(ann, ast.Subscript):
        toks |= annotation_tokens(ann.value)
        if ann.slice:
            toks |= annotation_tokens(ann.slice)
    elif isinstance(ann, ast.Attribute):
        toks |= annotation_tokens(ann.value)
    elif isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        toks |= annotation_tokens(ann.left)
        toks |= annotation_tokens(ann.right)
    return toks

def model_like_params(func):
    out = []
    for a in list(func.args.args) + list(func.args.kwonlyargs):
        if a.arg in ("self", "cls"):
            continue
        names = annotation_tokens(a.annotation) - BUILTIN_TYPES
        if names:
            out.append((a.arg, sorted(names)))
    return out

def order_aware_forward_ref_risk(tree):
    # collect module-level definitions with their source line
    defs = {}  # name -> min lineno where defined
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs.setdefault(node.name, node.lineno)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defs.setdefault(t.id, t.lineno)
        elif isinstance(node, (ast.ImportFrom, ast.Import)):
            for a in node.names:
                defs.setdefault((a.asname or a.name).split('.')[0], node.lineno)
    risks = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        fline = node.lineno
        # params
        for a in list(node.args.args) + list(node.args.kwonlyargs):
            if isinstance(a.annotation, ast.Constant) and isinstance(a.annotation.value, str):
                for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", a.annotation.value)):
                    if tok[0].isupper() and tok not in BUILTIN_TYPES and defs.get(tok, 1e9) > fline:
                        risks.add(f"{node.name}:{a.arg}->{tok}(defined@L{defs.get(tok)})")
        if isinstance(node.returns, ast.Constant) and isinstance(node.returns.value, str):
            for tok in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", node.returns.value)):
                if tok[0].isupper() and tok not in BUILTIN_TYPES and defs.get(tok, 1e9) > fline:
                    risks.add(f"{node.name}->ret {tok}(defined@L{defs.get(tok)})")
    return sorted(risks)

results = []
for dirpath, _, files in os.walk(API_ROOT):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            src = read(path)
            tree = ast.parse(src)
        except Exception as e:
            results.append((path, "PARSE_ERROR", str(e), [], []))
            continue
        if not has_future_import(tree):
            continue
        flagged = []
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not any(is_limiter_decorator(d) for d in node.decorator_list):
                continue
            mp = model_like_params(node)
            if mp:
                flagged.append((node.name, mp))
        if flagged:
            risks = order_aware_forward_ref_risk(tree)
            results.append((path, "DANGEROUS", "", flagged, risks))

print("=== FUTURE-IMPORT REMOVAL CANDIDATES ===")
safe, risky = [], []
for path, status, err, flagged, risks in results:
    rel = os.path.relpath(path, API_ROOT)
    if status == "PARSE_ERROR":
        print(f"\n[PARSE_ERROR] {rel}: {err}")
        continue
    line = f"{rel}"
    detail = ""
    for fname, mp in flagged:
        params = ", ".join(f"{p}:{','.join(ns)}" for p, ns in mp)
        detail += f"\n   @{fname}({params})"
    if risks:
        risky.append(rel)
        print(f"\n{rel}  [RISKY - forward-ref]")
        print(detail)
        print(f"   FORWARD-REF RISK: {risks}")
    else:
        safe.append(rel)
        print(f"\n{rel}  [SAFE]")
        print(detail)

print("\n=== SUMMARY ===")
print(f"SAFE to remove future import ({len(safe)}):")
for r in safe:
    print(f"  - {r}")
print(f"RISKY ({len(risky)}):")
for r in risky:
    print(f"  - {r}")
