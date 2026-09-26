"""Przeliczenia dla audytu twierdzeń README (TIMDR-Aviation-Diagnostics). Reguły: docs/audit/CLAIM_AUDIT_PREREG.md.

Część NIEZALEŻNA (własny kod): dane vs referencja train_FD001, ranking czujników, metoda A, test kształtu dryfu (R9),
porównanie AST rdzenia (R11). Część KOD REPO: analysis.py/timdr_core.py (metody pod testem) — wynik tabeli,
odtwarzanie przyczynowe (R8), sensor_scores (R12), pytest.
Użycie (katalog repo): python docs/audit/recompute_av.py  ->  docs/audit/RECOMPUTE_AV.json
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DATA = Path(os.environ.get("TIMDR_DATA", REPO.parent / "DATA"))
EQ_CORE = REPO.parent / "TIMDR-Earthquake-Core" / "core" / "timdr_core_earthquake.py"
LIT = {2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15, 17, 20, 21}
sys.path.insert(0, str(REPO))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def first_run(z: np.ndarray, run=3, thr=3.0):
    f = np.abs(z) > thr
    for i in range(len(f) - run + 1):
        if f[i:i + run].all():
            return i
    return None


def fn_ast(path: Path, names: set[str]) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            body = node.body[1:] if (node.body and isinstance(node.body[0], ast.Expr)
                                     and isinstance(getattr(node.body[0], "value", None), ast.Constant)
                                     and isinstance(node.body[0].value.value, str)) else node.body
            out[node.name] = ast.dump(ast.Module(body=body, type_ignores=[]))
    return out


def main():
    out = {}
    unit1 = np.loadtxt(REPO / "cmapss_fd001_unit1.txt")
    ref_path = DATA / "train_FD001.txt"
    ref = np.loadtxt(ref_path)
    ref1 = ref[ref[:, 0] == 1]
    out["data"] = {"shape": list(unit1.shape), "units_in_file": sorted(set(unit1[:, 0].astype(int).tolist())),
                   "cycles_first_last": [int(unit1[0, 1]), int(unit1[-1, 1])],
                   "cycles_consecutive": bool(np.all(np.diff(unit1[:, 1]) == 1)),
                   "ref_sha256": sha(ref_path), "ref_units": int(len(set(ref[:, 0].astype(int)))),
                   "ref_unit1_rows": int(len(ref1)),
                   "equal_to_ref_unit1": bool(ref1.shape == unit1.shape and np.array_equal(ref1, unit1))}

    # ranking czujnikow (niezaleznie)
    cyc, S = unit1[:, 1], unit1[:, 5:26]
    z = {}
    for j in range(21):
        a, b = S[:30, j], S[-30:, j]
        sd = a.std()
        if sd > 1e-12:
            z[j + 1] = float(abs(b.mean() - a.mean()) / sd)
    rank = sorted(z, key=lambda k: -z[k])
    out["sensors"] = {"n_scored": len(z), "top": rank[0], "rank": rank, "z": z,
                      "top14": sorted(rank[:14]), "top14_equals_literature": set(rank[:14]) == LIT,
                      "constant": sorted(set(range(1, 22)) - set(z))}

    # metoda A niezaleznie
    s4 = S[:, 3]
    za = (s4 - s4[:30].mean()) / s4[:30].std()
    ia = first_run(za)
    out["method_a_independent"] = {"alarm_cycle": int(cyc[ia]), "lead": int(cyc[-1] - cyc[ia]),
                                   "fp_1_60": bool(np.any(np.abs(za[:60]) > 3))}

    # R9 ksztalt dryfu
    x, y = cyc[30:], s4[30:]
    def fit(deg):
        c = np.polyfit(x, y, deg)
        rss = float(((np.polyval(c, x) - y) ** 2).sum())
        n = len(x)
        return c, n * np.log(rss / n) + (deg + 1) * np.log(n)
    c1, b1 = fit(1)
    c2, b2 = fit(2)
    third = len(x) // 3
    sl = [float(np.polyfit(x[i * third:(i + 1) * third], y[i * third:(i + 1) * third], 1)[0]) for i in (0, 2)]
    out["drift_shape"] = {"dbic_lin_minus_quad": float(b1 - b2), "curvature": float(c2[0]),
                          "slope_first_third": sl[0], "slope_last_third": sl[1], "slope_ratio": sl[1] / sl[0]}

    # R11 AST rdzenia
    names = {"__init__", "_safe_k", "_validate", "_nearest_k_bounds", "flow", "trm", "anomalies"}
    a, b = fn_ast(REPO / "timdr_core.py", names), fn_ast(EQ_CORE, names)
    out["core_ast"] = {"compared": sorted(names), "found_av": sorted(a), "found_eq": sorted(b),
                       "identical": {n: a.get(n) == b.get(n) for n in sorted(names)}}

    # KOD REPO: wynik tabeli
    import analysis
    r = analysis.compute_engine_run()
    out["repo_run"] = {m: {"alarm_cycle": r[m]["alarm_cycle"], "lead": r[m]["lead_time"],
                           "fp_1_60": r[m]["false_positive_1_60"], "anomaly_cycles": r[m]["anomaly_cycles"]}
                       for m in ("method_a", "method_b", "method_c")}
    out["repo_run"]["end_of_life"] = r["end_of_life"]
    out["repo_run"]["sensor_name"] = r["sensor_name"]

    # R8 odtwarzanie przyczynowe
    causal = {}
    for c_end in range(31, len(cyc) + 1):
        rr = analysis._analyze_series(cyc[:c_end], s4[:c_end], unit=1, sensor_name="s4", source="replay")
        last = c_end - 1
        for m, key in (("A", "method_a"), ("B", "method_b")):
            if m not in causal:
                zz = np.asarray(rr[key]["series"])
                if len(zz) >= 3 and np.all(np.abs(zz[last - 2:last + 1]) > 3.0):
                    causal[m] = int(cyc[last])
        if "C" not in causal and int(cyc[last]) in rr["method_c"]["anomaly_cycles"]:
            causal["C"] = int(cyc[last])
    out["causal"] = {m: {"known_at_cycle": c, "lead": int(cyc[-1] - c)} for m, c in causal.items()}

    # R12 sensor_scores
    best, scores = analysis.select_informative_sensor(cyc, S)
    raw = (REPO / "cmapss_fd001_unit1.txt").read_bytes()
    manual = analysis.compute_run_from_upload(raw, sensor=4)
    auto = analysis.compute_run_from_upload(raw)
    out["auto_select"] = {"best": best, "n_scores": len(scores), "manual_scores_is_none": manual["sensor_scores"] is None,
                          "auto_sensor_number": auto["sensor_number"], "auto_n_scores": len(auto["sensor_scores"] or {})}

    # pytest
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_analysis_extra.py"],
                       cwd=REPO, capture_output=True, text=True, timeout=150)
    out["pytest_analysis_extra"] = {"returncode": p.returncode, "tail": p.stdout.strip().splitlines()[-1:]}
    (HERE / "RECOMPUTE_AV.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    main()
