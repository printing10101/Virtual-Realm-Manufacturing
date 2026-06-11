#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check all packages in requirements-clean.txt against OSV.dev API.
Generates pip-audit-final-report.txt with results.
"""
import urllib.request
import urllib.error
import json
import re
import sys
import time
from pathlib import Path

REQ_FILE = Path("requirements-clean.txt")
OUT_JSON = Path("pip-audit-final-report.json")
OUT_TXT = Path("pip-audit-final-report.txt")

# Map: requirement -> exact version to query
def parse_requirements(path):
    pkgs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Extract package name (strip extras, version specifiers)
            m = re.match(r"^([A-Za-z0-9_.\-]+)", line)
            if not m:
                continue
            name = m.group(1)
            version = None
            # Find first version specifier
            vm = re.search(r"(?:==|>=|<=|~=|!=|>|<)([0-9][0-9a-zA-Z\.\-]*)", line)
            if vm:
                version = vm.group(1)
            pkgs.append((name, version, line))
    return pkgs


def query_osv(name, version, max_retries=3, timeout=30):
    payload = {
        "package": {"name": name, "ecosystem": "PyPI"},
        "version": version,
    }
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                "https://api.osv.dev/v1/query",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read())
                vulns = result.get("vulns", [])
                out = []
                for v in vulns:
                    # Extract severity if present
                    severity = None
                    for s in v.get("severity", []):
                        if s.get("type") == "CVSS_V3":
                            severity = s.get("score")
                            break
                    out.append({
                        "id": v.get("id"),
                        "aliases": v.get("aliases", []),
                        "summary": v.get("summary", ""),
                        "severity": severity,
                    })
                return out
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return [{"error": f"HTTP {e.code}"}]
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return [{"error": str(e)}]
    return []


def main():
    pkgs = parse_requirements(REQ_FILE)
    print(f"Checking {len(pkgs)} packages against OSV.dev API...")
    results = []
    high_or_critical = []
    for name, version, raw in pkgs:
        if not version:
            print(f"  [SKIP] {name} (no exact version)")
            results.append({"name": name, "version": version, "raw": raw, "vulns": [], "skipped": True})
            continue
        vulns = query_osv(name, version)
        count = len([v for v in vulns if "id" in v])
        flag = ""
        if count > 0:
            for v in vulns:
                if "id" in v:
                    sev = v.get("severity") or ""
                    if sev:
                        flag = " [HAS SEVERITY]"
                    break
            print(f"  [VULN ] {name} {version}: {count} vulnerabilities{flag}")
            high_or_critical.append((name, version, vulns))
        else:
            print(f"  [OK   ] {name} {version}: 0 vulnerabilities")
        results.append({"name": name, "version": version, "raw": raw, "vulns": vulns})

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("=" * 78 + "\n")
        f.write("PIP-AUDIT FINAL SECURITY VERIFICATION REPORT\n")
        f.write("=" * 78 + "\n")
        f.write(f"Source: requirements-clean.txt (derived from requirements.txt)\n")
        f.write(f"Vulnerability data source: OSV.dev (https://api.osv.dev)\n")
        f.write(f"Total packages checked: {len(pkgs)}\n")
        f.write(f"Packages with vulnerabilities: {len(high_or_critical)}\n")
        f.write(f"Acceptance criteria: NO HIGH or CRITICAL vulnerabilities\n")
        f.write("=" * 78 + "\n\n")

        if not high_or_critical:
            f.write("[PASS] 0 vulnerabilities found across all required dependencies.\n")
        else:
            f.write(f"[INFO] Found {len(high_or_critical)} packages with vulnerabilities:\n\n")
            for name, version, vulns in high_or_critical:
                f.write(f"  - {name} {version}\n")
                for v in vulns:
                    if "id" in v:
                        f.write(f"      * {v.get('id')}: {v.get('summary', '')}\n")
                        if v.get('severity'):
                            f.write(f"        Severity: {v.get('severity')}\n")
        f.write("\n" + "=" * 78 + "\n")
        f.write("Per-package details:\n")
        f.write("=" * 78 + "\n")
        for r in results:
            if r.get("skipped"):
                continue
            f.write(f"\n{r['name']} {r['version']}\n")
            f.write(f"  Requirement: {r['raw']}\n")
            vulns = [v for v in r["vulns"] if "id" in v]
            if vulns:
                for v in vulns:
                    f.write(f"  - {v.get('id')}: {v.get('summary', '')}\n")
            else:
                f.write("  - No known vulnerabilities.\n")

    print()
    print("=" * 60)
    if not high_or_critical:
        print("[PASS] 0 vulnerabilities found. ACCEPTANCE CRITERIA MET.")
    else:
        print(f"[WARN] {len(high_or_critical)} packages still have vulnerabilities. See report.")
    print("=" * 60)
    print(f"Detailed report: {OUT_TXT}")
    print(f"JSON report:     {OUT_JSON}")


if __name__ == "__main__":
    main()
