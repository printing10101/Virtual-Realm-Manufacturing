import ast, os, sys

API_ROOT = r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\engineering\python\app"

def local_base_models(tree):
    names = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                # detect BaseModel in bases (BaseModel or pydantic.BaseModel)
                if isinstance(base, ast.Name) and base.id == "BaseModel":
                    names.add(node.name)
                elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                    names.add(node.name)
    return names

def module_defined_names(tree):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
    # imports
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                names.add(a.asname or a.name)
        elif isinstance(node, ast.Import):
            for a in node.names:
                names.add((a.asname or a.name).split('.')[0])
    return names

def is_limiter_decorator(dec):
    # match @limiter.limit(...)  -> Call(func=Attribute(value=Name('limiter'), attr='limit'))
    if isinstance(dec, ast.Call):
        f = dec.func
    else:
        f = dec
    if isinstance(f, ast.Attribute) and f.attr == "limit":
        if isinstance(f.value, ast.Name) and f.value.id == "limiter":
            return True
    return False

def param_annotation_references_local_model(func, local_models):
    # With future import, annotations are strings (ast.Constant str) OR actual nodes.
    hits = []
    for arg in func.args.args + func.args.kwonlyargs:
        ann = arg.annotation
        if ann is None:
            continue
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            text = ann.value
            for m in local_models:
                if text == m or text.startswith(m + "[" ) or text.startswith(m + "(") or (m in text.split()):
                    hits.append((arg.arg, m, text))
                    break
        elif isinstance(ann, ast.Name) and ann.id in local_models:
            hits.append((arg.arg, ann.id, ann.id))
        elif isinstance(ann, ast.Subscript) and isinstance(ann.value, ast.Name) and ann.value.id in local_models:
            hits.append((arg.arg, ann.value.id, ann.value.id))
    return hits

def has_future_import(tree):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            for a in node.names:
                if a.name == "annotations":
                    return True
    return False

dangerous = []
for dirpath, _, files in os.walk(API_ROOT):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception as e:
            print(f"PARSE ERROR {path}: {e}")
            continue
        if not has_future_import(tree):
            continue
        local_models = local_base_models(tree)
        if not local_models:
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.decorator_list:
                continue
            if not any(is_limiter_decorator(d) for d in node.decorator_list):
                continue
            hits = param_annotation_references_local_model(node, local_models)
            if hits:
                rel = os.path.relpath(path, API_ROOT)
                dangerous.append((rel, node.name, hits))

print("=== DANGEROUS FILES (future import + limiter-wrapped endpoint + local pydantic body param) ===")
for rel, fname, hits in dangerous:
    print(f"\n{rel} :: {fname}")
    for arg, model, text in hits:
        print(f"    param '{arg}' -> {model}  (annotation: {text})")
if not dangerous:
    print("NONE FOUND")
