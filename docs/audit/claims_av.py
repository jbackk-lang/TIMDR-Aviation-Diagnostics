"""Karty twierdzeń README (TIMDR-Aviation-Diagnostics) dla tools/claim_audit.py.
Reguły: docs/audit/CLAIM_AUDIT_PREREG.md + CLAIM_AUDIT_ADDENDUM_1.md. Przeliczenia: docs/audit/RECOMPUTE_AV.json.

v1.1 (po przebiegu 1 i poprawce README): nowe cytaty V6, V7, V19; V18 oceniane wzorcem alarmów online; nowe karty V21
(odtwarzanie na bieżąco) i V22 (przyszłe cykle w B/C); R6 z ujawnieniem; „zawsze używa” pominięte w R7b.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools"))
from claim_audit import POTWIERDZONE, SPRZECZNE, NIEROZSTRZYGNIETE, UDOKUMENTOWANE, Claim, Result  # noqa: E402

TITLE = "README → dane, metodologia, wynik, auto-wybór czujnika, pliki (TIMDR-Aviation-Diagnostics)"
README = "README.md"
PREREG = "docs/audit/CLAIM_AUDIT_PREREG.md"
OUTPUT = "CLAIM_AUDIT.md"
SCOPES = [(r"^## Co jest tu realne", r"^## Jak zrobić"), (r"^### Auto-wybór", r"^## Pliki"), (r"^## Pliki", r"^@@@KONIEC")]
DO_ZLAGODZENIA = "DO ZŁAGODZENIA"


def rc() -> dict:
    return json.loads((HERE / "RECOMPUTE_AV.json").read_text(encoding="utf-8"))


def src(name: str) -> str:
    return (REPO / name).read_text(encoding="utf-8")


def R(ok, value, note="", bad=SPRZECZNE):
    return Result(POTWIERDZONE if ok else bad, value, note)


# ---------------------------------------------------------------- dane
def v_env():
    return Result(NIEROZSTRZYGNIETE, "-", "historia środowiska, w którym powstało repo - nieweryfikowalna z plików")


def v_run():
    d = rc()["data"]
    ok = d["units_in_file"] == [1] and d["cycles_first_last"] == [1, 192] and d["cycles_consecutive"] \
        and d["shape"][1] - 5 == 21 and d["ref_unit1_rows"] == 192
    return R(ok, f"unit {d['units_in_file']}, cykle {d['cycles_first_last'][0]}–{d['cycles_first_last'][1]} bez luk, "
             f"{d['shape'][1] - 5} czujników; w train_FD001 unit 1 kończy się na cyklu {d['ref_unit1_rows']}",
             "poziom REFERENCJA (zbiór treningowy C-MAPSS: przebiegi do awarii)")


def v_copy():
    d = rc()["data"]
    return R(d["equal_to_ref_unit1"] and d["ref_sha256"].startswith("963b5e22"),
             "192 wiersze identyczne liczbowo z unit 1 w train_FD001.txt z mirrora mapr-demos", "poziom REFERENCJA")


def v_n1():
    return R(rc()["data"]["units_in_file"] == [1], "jedna jednostka w pliku", "")


def v_100():
    n = rc()["data"]["ref_units"]
    return R(n == 100, f"train_FD001.txt: {n} silników", "poziom REFERENCJA")


def v_select():
    s = rc()["sensors"]
    ok = s["top"] == 4
    return Result(DO_ZLAGODZENIA if ok else SPRZECZNE, f"największy z-score: czujnik {s['top']} "
                  f"(z = {s['z'][str(s['top'])]:.1f})".replace(".", ","),
                  "R13: wybór jest algorytmiczny, ale używa ostatnich 30 cykli (koniec życia) tego samego silnika, na którym "
                  "mierzy się czas ostrzeżenia - README tego nie mówi; nazwa T50 wg dokumentacji C-MAPSS (nie z pliku)")


def v_literature():
    s = rc()["sensors"]
    extra = sorted(set(s["top14"]) - {2, 3, 4, 7, 8, 9, 11, 12, 13, 14, 15, 17, 20, 21})
    return R(s["top14_equals_literature"], f"top-14: {s['top14']}; czujniki stałe: {s['constant']}",
             "R10" + (f"; poza zestawem z literatury: {extra}" if extra else ""))


def v_rule_a():
    a = src("analysis.py")
    ok = "def first_sustained_alarm(z: np.ndarray, run: int = 3, thr: float = 3.0)" in a and "MIN_SAMPLES = 30" in a
    return R(ok, "first_sustained_alarm(run=3, thr=3.0), okno referencyjne 30", "")


def v_rule_b():
    ok = "TIMDR_EarthquakeCore(k_neighbors=8)" in src("analysis.py") and "np.linalg.lstsq" in src("timdr_core.py")
    return R(ok, "k_neighbors=8, gradient z lstsq", "okno k najbliższych cykli z obu stron (także przyszłych) - patrz R8")


def v_rule_c():
    ok = "core.anomalies(cycle, sensor, factor=3.0)" in src("analysis.py") and "mad_scale=1.4826" in src("timdr_core.py")
    return R(ok, "factor=3.0, MAD ×1,4826", "próg MAD liczony z całego przebiegu (także przyszłych cykli) - patrz R8")


def _row(m, cyc, lead):
    r, ind = rc()["repo_run"][m], rc()["method_a_independent"]
    ok = r["alarm_cycle"] == cyc and r["lead"] == lead and r["fp_1_60"] is False
    note = "poziom KOD REPO"
    if m == "method_a":
        ok = ok and ind["alarm_cycle"] == cyc and ind["lead"] == lead and not ind["fp_1_60"]
        note = "poziom KOD REPO + NIEZALEŻNE (metoda A przeliczona własnym kodem)"
    return R(ok, f"alarm {r['alarm_cycle']}, lead {r['lead']}, fałszywy alarm 1-60: {r['fp_1_60']}", note)


def v_a():
    return _row("method_a", 145, 47)


def v_b():
    return _row("method_b", 174, 18)


def v_c():
    r = rc()["repo_run"]["method_c"]
    fp = any(c <= 60 for c in r["anomaly_cycles"])
    ok = r["alarm_cycle"] == 96 and r["lead"] == 96 and not fp
    return R(ok, f"pierwsza anomalia {r['alarm_cycle']}, lead {r['lead']}, anomalie ≤ 60: {fp}",
             "R14: pole false_positive_1_60 dla C jest w kodzie ustawione na False bez obliczeń; tu policzone z listy")


def v_fp_header():
    r = rc()["repo_run"]
    fps = [r["method_a"]["fp_1_60"], r["method_b"]["fp_1_60"], any(c <= 60 for c in r["method_c"]["anomaly_cycles"])]
    return R(not any(fps), f"A {fps[0]}, B {fps[1]}, C {fps[2]}", "R14")


def v_iso():
    a = rc()["repo_run"]["method_c"]["anomaly_cycles"]
    iso = all(b - x > 1 for x, b in zip(a, a[1:]))
    return R(a == [96, 126, 165] and iso, f"anomalie: {a}", "")


def v_96():
    return R(rc()["repo_run"]["method_c"]["alarm_cycle"] == 96, "pierwsza anomalia 96", "")


def v_causal():
    c, readme = rc()["causal"], {"A": 47, "B": 18, "C": 96}
    parts, ok = [], True
    for m, lead in readme.items():
        got = c.get(m, {}).get("lead")
        tol = 2 if m in "AB" else 0
        good = got is not None and got >= lead - tol
        ok &= good
        parts.append(f"{m}: README {lead}, przyczynowo {got if got is not None else 'brak alarmu'}")
    return R(ok, "; ".join(parts), "R8: metoda dostaje tylko cykle 1..c")


def v_a_better():
    r, c = rc()["repo_run"], rc()["causal"]
    ok = r["method_a"]["lead"] > r["method_b"]["lead"] and c.get("A", {}).get("lead", -1) > c.get("B", {}).get("lead", -1)
    return R(ok, f"lead A {r['method_a']['lead']} vs B {r['method_b']['lead']} (przyczynowo "
             f"{c.get('A', {}).get('lead')} vs {c.get('B', {}).get('lead')})", "")


def v_drift():
    d = rc()["drift_shape"]
    accel = d["dbic_lin_minus_quad"] > 10 and d["curvature"] > 0 and d["slope_ratio"] >= 2
    return Result(SPRZECZNE if accel else POTWIERDZONE,
                  f"ΔBIC lin−kwadr {d['dbic_lin_minus_quad']:.1f}, krzywizna {d['curvature']:.2e}, nachylenie ostatniej/"
                  f"pierwszej trzeciej {d['slope_ratio']:.1f}×".replace(".", ","), "R9, czujnik 4, cykle 31–192")


def v_select_v11():
    s = rc()["sensors"]
    return R(s["top"] == 4, f"największy z-score: czujnik {s['top']} (z = {s['z'][str(s['top'])]:.1f})".replace(".", ","),
             "R13: selekcja na wyniku opisana w README")


def v_literature_v11():
    s = rc()["sensors"]
    ok = s["top14_equals_literature"] and len(s["constant"]) == 7 and s["n_scored"] == 14
    return R(ok, f"niestałe: {sorted(s['top14'])}; stałe: {s['constant']}", "R10")


def v_drift_v11():
    d = rc()["drift_shape"]
    ok = d["dbic_lin_minus_quad"] > 10 and d["curvature"] > 0 and abs(d["slope_ratio"] - 27) <= 0.15 * 27
    return R(ok, f"ΔBIC {d['dbic_lin_minus_quad']:.1f}, nachylenie ostatniej/pierwszej trzeciej {d['slope_ratio']:.1f}×"
             .replace(".", ","), "R9")


def v_a_better_v11():
    r, o = rc()["repo_run"], rc()["online"]
    ok = r["method_a"]["lead"] > r["method_b"]["lead"] and o["A"]["share_after_first"] >= 0.9 \
        and o["B"]["share_after_first"] < 0.25 and o["C"]["share_after_first"] < 0.25
    return R(ok, f"wstecznie lead A {r['method_a']['lead']} vs B {r['method_b']['lead']}; online odsetek cykli z alarmem "
             f"po pierwszym: A {o['A']['share_after_first']:.2f}, B {o['B']['share_after_first']:.2f}, "
             f"C {o['C']['share_after_first']:.2f}".replace(".", ","), "„pewniejszy” = trwały alarm online")


def v_online():
    o = rc()["online"]
    ok = o["A"]["cycles"][0] == 147 and 192 - 147 == 45 and o["A"]["share_after_first"] >= 0.9 \
        and o["B"]["cycles"][0] == o["C"]["cycles"][0] == 87 and o["B"]["n"] == 8 and o["C"]["n"] == 5 \
        and o["B"]["share_after_first"] < 0.25 and o["C"]["share_after_first"] < 0.25
    return R(ok, f"A od {o['A']['cycles'][0]} ({o['A']['n']} cykli); B {o['B']['cycles']}; C {o['C']['cycles']}",
             "odtwarzanie online (aneks 1)")


def v_future():
    core = src("timdr_core.py")
    ok = "lo, hi = self._nearest_k_bounds(t, i, k)" in core and "smooth = self.trm(t, s)" in core \
        and "mad = np.median(np.abs(residuals)) * self.mad_scale" in core
    return R(ok, "flow/trm: okno k najbliższych po obu stronach; anomalies: MAD z reszt całego szeregu", "")


def v_c_earliest():
    c = rc()["causal"]
    leads = {m: c.get(m, {}).get("lead", -1) for m in "ABC"}
    ok = leads["C"] >= max(leads["A"], leads["B"])
    return R(ok, f"lead przyczynowy: A {leads['A']}, B {leads['B']}, C {leads['C']}", "oceniane przyczynowo (R8)")


# ---------------------------------------------------------------- auto-wybor
def a_date():
    d = subprocess.run(["git", "-C", str(REPO), "log", "--format=%cs", "-S", "def select_informative_sensor", "--",
                        "analysis.py"], capture_output=True, text=True).stdout.split()
    return R(d[-1:] == ["2026-09-22"], f"funkcja dodana w commicie z {d[-1] if d else '-'}", "")


def a_engine4():
    a = src("analysis.py")
    ok = "SENSOR4_COL = 5 + 3" in a and "sensor = data[:, SENSOR4_COL]" in a
    return R(ok, "compute_engine_run: kolumna SENSOR4_COL (czujnik 4)", "")


def a_upload_auto():
    ok = "raw_bytes: bytes, unit: int | None = None, sensor: int | None = None" in src("analysis.py")
    return R(ok and rc()["auto_select"]["auto_sensor_number"] == 4, "upload: sensor=None -> auto-wybór", "")


def a_formula():
    s, a = rc()["sensors"], rc()["auto_select"]
    ok = a["best"] == s["top"] == 4
    return R(ok, f"repo i niezależne przeliczenie: najlepszy czujnik {a['best']}; ocenionych {a['n_scores']} z 21",
             "czujniki o stałej wartości w oknie referencyjnym są pomijane")


def a_reproduces():
    ok = rc()["auto_select"]["best"] == 4 and rc()["pytest_analysis_extra"]["returncode"] == 0 \
        and "def test_select_informative_sensor_reproduces_sensor4_on_real_unit1" in src("test_analysis_extra.py")
    return R(ok, f"best = 4; pytest: {rc()['pytest_analysis_extra']['tail']}", "")


def a_all21():
    n = rc()["auto_select"]["n_scores"]
    return R(n == 21, f"sensor_scores ma {n} wpisów", "R12" + ("" if n == 21 else f"; pominięte czujniki stałe: "
                                                              f"{rc()['sensors']['constant']}"))


def a_null():
    return R(rc()["auto_select"]["manual_scores_is_none"], "sensor=4 podany ręcznie -> sensor_scores = None", "")


# ---------------------------------------------------------------- pliki
def p_data():
    d = rc()["data"]
    return R(d["shape"] == [192, 26] and d["equal_to_ref_unit1"], f"{d['shape'][0]} × {d['shape'][1]}", "poziom REFERENCJA")


def p_core():
    c = rc()["core_ast"]
    ok = all(c["identical"].values()) and c["found_av"] == c["found_eq"] == c["compared"]
    diff = [n for n, v in c["identical"].items() if not v]
    return R(ok, "funkcje metod identyczne (AST bez docstringów)" if ok else f"różne: {diff}",
             "R11; poza nimi różni się obsługa importu scipy (leniwy import), tak jak w źródle po późniejszej poprawce")


def p_shared():
    ok = "from analysis import compute_engine_run" in src("test_engine_degradation.py") and "analysis" in src("webapp/app.py")
    return R(ok, "import analysis w obu", "")


def p_tests():
    t = src("test_analysis_extra.py")
    names = ("test_compute_engine_run_unit1_unchanged", "test_synthetic_run", "test_upload", "test_device_samples",
             "test_dominant_frequency")
    ok = all(n in t for n in names) and rc()["pytest_analysis_extra"]["returncode"] == 0
    return R(ok, f"testy obecne dla 5 grup; pytest: {rc()['pytest_analysis_extra']['tail']}", "")


CLAIMS = [
    Claim("V1", "wszystkie zwracają `403 blocked-by-allowlist` na poziomie bash", v_env),
    Claim("V2", "(FD001, unit 1, kompletny przebieg run-to-failure — 192 cykle, 21 czujników, awaria w cyklu 192)", v_run),
    Claim("V3", "Plik `cmapss_fd001_unit1.txt` w tym repo to dokładna kopia tych 192 wierszy z oryginalnego `train_FD001.txt`", v_copy),
    Claim("V4", "**To jest test na n=1 (jeden silnik)**", v_n1),
    Claim("V5", "(do tego potrzeba pełnego zbioru 100 silników", v_100),
    Claim("V6", "Czujnik do testu (sensor 4, T50 — temperatura na wylocie z LPT) dobrano **algorytmicznie**: spośród 21 "
                "czujników wybrano ten o największym przesunięciu średniej między ostatnimi 30 a pierwszymi 30 cyklami",
          v_select_v11),
    Claim("V7", "14 czujników o niezerowej zmienności to dokładnie znany z literatury zbiór ok. 14 \"informative sensors\" "
                "dla FD001 (pozostałe 7 jest stałych)", v_literature_v11),
    Claim("V8", "3 kolejne cykle z \\|z\\|>3 względem pierwszych 30 cykli", v_rule_a),
    Claim("V9", "lokalny trend (gradient LSQ, k=8)", v_rule_b),
    Claim("V10", "domyślny próg factor=3.0×MAD", v_rule_c),
    Claim("V11", "Fałszywy alarm w cyklach 1-60", v_fp_header),
    Claim("V12", "| A — baseline SPC (wartość) | 145 | **47** | nie |", v_a),
    Claim("V13", "| B — TIMDR flow (trend) | 174 | **18** | nie |", v_b),
    Claim("V14", "| C — TIMDR anomalies | 96 (izolowany) | **96*** | nie (ale niepotwierdzone, patrz niżej) |", v_c),
    Claim("V15", "Lead time (cykli przed awarią)", v_causal),
    Claim("V16", "Metoda C zgłasza 3 pojedyncze, izolowane punkty (cykle 96, 126, 165), nie sygnał ciągły", v_iso),
    Claim("V17", "traktuj cykl 96 jako obiecujący trop, nie potwierdzony wynik", v_96),
    Claim("V18", "metoda A) dał lepszy, pewniejszy wynik niż przeniesiony bez zmian mechanizm `flow` (metoda B)", v_a_better_v11),
    Claim("V19", "przy dryfie degradacyjnym, który jest prawie płaski przez większość życia i przyspiesza pod koniec "
                 "(nachylenie w ostatniej trzeciej części ok. 27× większe niż w pierwszej)", v_drift_v11),
    Claim("V20", "`anomalies()` dał najwcześniejszy sygnał", v_c_earliest),
    Claim("V21", "Przy odtwarzaniu na bieżąco (metoda widzi tylko cykle do bieżącego) A alarmuje trwale od cyklu 147 "
                 "(lead 45), a B i C dają pojedyncze, rozproszone alarmy już od cyklu 87 (B w 8 cyklach, C w 5)", v_online),
    Claim("V22", "metody B i C korzystają przy tym z przyszłych cykli (B: gradient z k=8 najbliższych cykli z obu stron; "
                 "C: mediana z obu stron i próg MAD z całego przebiegu)", v_future),
    Claim("A1", "### Auto-wybór czujnika dla wgranego pliku (2026-09-22)", a_date),
    Claim("A2", "`compute_engine_run()` (jedyne realne dane, unit=1) zawsze używa sensora 4", a_engine4),
    Claim("A3", "sensor 4 nie ma tam żadnego uprzywilejowanego statusu", a_upload_auto),
    Claim("A4", "liczy dla wszystkich 21 czujników ten sam z-score przesunięcia średniej (ostatnie 30 cykli względem pierwszych "
                "30, znormalizowane odchyleniem standardowym okna referencyjnego), którym pierwotnie RĘCZNIE znaleziono "
                "sensor 4 dla unit=1", a_formula),
    Claim("A5", "na danych unit=1 auto-wybór odtwarza dokładnie sensor 4 (patrz "
                "`test_select_informative_sensor_reproduces_sensor4_on_real_unit1` w `test_analysis_extra.py`)", a_reproduces),
    Claim("A6", "(wszystkie 21 wyników z-score, żeby wybór był audytowalny, nie czarną skrzynką)", a_all21),
    Claim("A7", "`sensor_scores` jest `null`, gdy `sensor` podano ręcznie", a_null),
    Claim("P1", "`cmapss_fd001_unit1.txt` — realne dane NASA C-MAPSS FD001, unit 1 (192 cykle × 26 kolumn: unit, cycle, "
                "3×operational setting, 21×sensor)", p_data),
    Claim("P2", "`timdr_core.py` — kopia 1:1 `timdr_core_earthquake.py` z `TIMDR-Earthquake-Core` (bez zmian logiki)", p_core),
    Claim("P3", "używany zarówno przez `test_engine_degradation.py`, jak i `webapp/app.py`", p_shared),
    Claim("P4", "`test_analysis_extra.py` — testy funkcji obliczeniowych dla 4 źródeł danych (regresja unit=1, demo syntetyczne, "
                "upload, próbki z urządzenia, ekstrakcja dominującej częstotliwości z audio)", p_tests),
]

FROZEN = {"../DATA/train_FD001.txt": "963b5e22825b34d8b21c69e1aeb4af3e647050eb672ee8834ba4b5d91d2de0f8"}
ANCHORS = [("test_engine_degradation.py", "README.md")]
ANCHOR_DISCLOSURE = r"w tym samym commicie \(d3a6ddf\)"
FORBIDDEN = [(r"wczesn\w+\s+ostrzeż\w*", r"\bnie\b|niepotwierdz|trop", "brak kontroli negatywnej i n = 1"),
             (r"walidacj\w*\s+statystyczn\w*", r"\bnie\b", "n = 1")]
ABSOLUTE = [(r"\btak samo\b", "podaj różnicę"), (r"\bzawsze\b(?! używa sensora 4)|\bnigdy\b", "słowo bezwzględne"),
            (r"\bdowodzi\b|\budowodni\w*", "„dowodzi” wymaga dowodu"), (r"(?<!\d)100 ?%", "sprawdź liczność")]
