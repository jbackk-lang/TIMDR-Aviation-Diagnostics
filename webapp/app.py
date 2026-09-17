"""
webapp/app.py — lokalna appka (FastAPI) dla TIMDR-Aviation-Diagnostics.

Ten sam wybor architektoniczny co Synoptyk-v3/SYNOPTYK-ARCTIC (patrz
tamte webapp/app.py): prawdziwa mala appka, nie statyczny HTML z
wbudowanymi danymi na sztywno. Roznica wzgledem tamtych dwoch: dane tu sa
STATYCZNE (jeden plik CSV, jeden realny silnik, n=1 -- patrz README) --
wiec brak tu /api/collect ani zadnego "zbierania" na zywo, jest tylko
JEDEN endpoint danych, ktory za kazdym razem przelicza metody A/B/C z
analysis.py (ten sam kod, ktorego uzywa test_engine_degradation.py) i
oddaje kompletny wynik do wykresow.

Endpointy:
- GET /              — dashboard (statyczny HTML+JS, wykresy SVG)
- GET /api/engine_run — pelny wynik compute_engine_run(): serie
                        surowego czujnika, z-score metod A/B, residua
                        metody C, cykle alarmow, lead time, falszywe
                        alarmy. Parametr ?unit= zaakceptowany na
                        przyszlosc (patrz README "Jak zrobic to
                        porzadnie"), ale na razie wspiera WYLACZNIE
                        unit=1 -- inne wartosci daja czytelny HTTP 400,
                        nie cichy zly wynik.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from analysis import compute_engine_run  # noqa: E402

app = FastAPI(title="TIMDR-Aviation-Diagnostics dashboard")

_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    index_path = _STATIC_DIR / "index.html"
    return index_path.read_text(encoding="utf-8")


@app.get("/api/engine_run")
def api_engine_run(unit: int = 1):
    try:
        return compute_engine_run(unit=unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="cmapss_fd001_unit1.txt nie znaleziony -- uruchamiasz z "
            "wlasciwego katalogu? (patrz README, sekcja Uruchomienie)",
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
