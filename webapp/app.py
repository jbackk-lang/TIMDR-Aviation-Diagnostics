"""
webapp/app.py — lokalna appka (FastAPI) dla TIMDR-Aviation-Diagnostics.

Ten sam wybor architektoniczny co Synoptyk-v3/SYNOPTYK-ARCTIC (patrz
tamte webapp/app.py): prawdziwa mala appka, nie statyczny HTML z
wbudowanymi danymi na sztywno.

Endpointy:
- GET  /                — dashboard (statyczny HTML+JS, wykresy SVG)
- GET  /api/engine_run   — realne dane, unit=1 (jedyne realne dane w tym
                            repo). Parametr ?unit= przyjety na przyszlosc,
                            ale na razie wspiera WYLACZNIE unit=1.
- GET  /api/synthetic_run     — SYNTETYCZNY drugi przebieg, jawnie
                                 oznaczony, do demonstracji UI (patrz
                                 analysis.compute_synthetic_run).
- POST /api/upload             — wlasny plik uzytkownika w formacie
                                 C-MAPSS (multipart/form-data, pole
                                 "file"), opcjonalny query param ?unit=.
- GET  /api/serial/ports        — lista dostepnych portow szeregowych
                                 (wymaga pyserial; jesli niedostepne,
                                 HTTP 501).
- POST /api/serial/read          — odczyt N probek z podanego portu
                                 szeregowego i analiza tym samym rdzeniem
                                 A/B/C. UWAGA: ten kod NIE zostal
                                 przetestowany na prawdziwym urzadzeniu w
                                 srodowisku, w ktorym powstal (sandbox bez
                                 dostepu do portow szeregowych) -- patrz
                                 README, sekcja "Zrodlo: urzadzenie".
- GET  /api/audio/devices        — lista urzadzen audio z wejsciem (w tym
                                 sparowane sluchawki/zestawy Bluetooth
                                 widoczne w systemie jako urzadzenie
                                 wejsciowe) -- wymaga sounddevice; jesli
                                 niedostepne, HTTP 501.
- POST /api/audio/record          — nagrywa audio z wybranego urzadzenia i
                                 liczy dominujaca czestotliwosc (FFT) w
                                 kolejnych oknach czasowych jako serie
                                 probek dla tego samego rdzenia A/B/C
                                 (patrz analysis.dominant_frequency_series
                                 -- ta ekstrakcja cechy JEST przetestowana
                                 syntetycznie; sam odczyt z prawdziwego
                                 mikrofonu/Bluetooth NIE, z tego samego
                                 powodu co /api/serial/read).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import sys as _sys
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_REPO_ROOT))

from analysis import (  # noqa: E402
    compute_engine_run,
    compute_run_from_device_samples,
    compute_run_from_upload,
    compute_synthetic_run,
    dominant_frequency_series,
)

# pyserial i sounddevice sa OPCJONALNE -- ten sam wzorzec co scipy w
# timdr_core.py (patrz commit "Napraw import scipy..."): brak pakietu /
# zablokowany import / brak sprzetu nie moze wywrocic calej appki, tylko
# wylaczyc odpowiednia grupe endpointow.
try:
    import serial  # pyserial
    import serial.tools.list_ports as _list_ports
    _HAS_SERIAL = True
except ImportError:
    _HAS_SERIAL = False

_SERIAL_UNAVAILABLE_MSG = (
    "pyserial niedostepny w tym srodowisku (pakiet niezainstalowany lub "
    "zablokowany) -- zainstaluj 'pip install pyserial' (jest w "
    "requirements.txt) i uruchom ponownie."
)

try:
    import sounddevice as _sd
    _HAS_AUDIO = True
except (ImportError, OSError):
    # OSError -- sounddevice zainstalowany, ale biblioteka natywna
    # PortAudio niedostepna w systemie (typowy blad na "golym" Linuxie
    # bez libportaudio2, moze sie zdarzyc tez na zablokowanym Windows).
    _HAS_AUDIO = False

_AUDIO_UNAVAILABLE_MSG = (
    "sounddevice niedostepny w tym srodowisku (pakiet niezainstalowany, "
    "brak biblioteki PortAudio, lub brak urzadzenia audio) -- zainstaluj "
    "'pip install sounddevice' (jest w requirements.txt) i uruchom "
    "ponownie."
)

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


@app.get("/api/synthetic_run")
def api_synthetic_run(seed: int = 42):
    try:
        return compute_synthetic_run(seed=seed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...), unit: Optional[int] = None):
    raw = await file.read()
    try:
        return compute_run_from_upload(raw, unit=unit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/serial/ports")
def api_serial_ports():
    if not _HAS_SERIAL:
        raise HTTPException(status_code=501, detail=_SERIAL_UNAVAILABLE_MSG)
    ports = _list_ports.comports()
    return [{"device": p.device, "description": p.description or ""} for p in ports]


@app.post("/api/serial/read")
def api_serial_read(port: str, baud: int = 9600, samples: int = 60, timeout_s: float = 2.0):
    if not _HAS_SERIAL:
        raise HTTPException(status_code=501, detail=_SERIAL_UNAVAILABLE_MSG)
    if samples < 30:
        raise HTTPException(status_code=400, detail="samples musi byc >= 30 (okno referencyjne).")

    values: list[float] = []
    try:
        with serial.Serial(port, baud, timeout=timeout_s) as ser:
            while len(values) < samples:
                line = ser.readline()
                if not line:
                    break  # timeout bez danych -- konczymy z tym, co mamy
                try:
                    values.append(float(line.decode("utf-8", errors="ignore").strip()))
                except ValueError:
                    continue  # pomin nie-numeryczna linie (np. naglowek/smiecie)
    except serial.SerialException as e:
        raise HTTPException(status_code=500, detail=f"blad portu szeregowego: {e}")

    if len(values) < 30:
        raise HTTPException(
            status_code=502,
            detail=f"odebrano tylko {len(values)} poprawnych probek liczbowych "
            f"przed timeoutem/koncem strumienia -- potrzeba co najmniej 30. "
            f"Sprawdz baud rate i format danych wysylanych przez urzadzenie "
            f"(oczekiwana jedna liczba na linie).",
        )
    try:
        return compute_run_from_device_samples(values, port_label=port)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/audio/devices")
def api_audio_devices():
    if not _HAS_AUDIO:
        raise HTTPException(status_code=501, detail=_AUDIO_UNAVAILABLE_MSG)
    try:
        devices = _sd.query_devices()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"blad odczytu listy urzadzen audio: {e}")
    return [
        {"index": i, "name": d["name"], "max_input_channels": d["max_input_channels"]}
        for i, d in enumerate(devices)
        if d["max_input_channels"] > 0
    ]


@app.post("/api/audio/record")
def api_audio_record(device: int, duration_s: float = 20.0, window_s: float = 0.5, samplerate: int = 16000):
    if not _HAS_AUDIO:
        raise HTTPException(status_code=501, detail=_AUDIO_UNAVAILABLE_MSG)
    if window_s <= 0 or duration_s / window_s < 30:
        raise HTTPException(
            status_code=400,
            detail=f"duration_s/window_s musi dac co najmniej 30 okien (okno "
            f"referencyjne); teraz {duration_s / window_s if window_s > 0 else 0:.1f}.",
        )

    try:
        n_samples = int(duration_s * samplerate)
        audio = _sd.rec(n_samples, samplerate=samplerate, channels=1, dtype="float32", device=device)
        _sd.wait()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"blad nagrywania audio: {e}")

    values = dominant_frequency_series(audio[:, 0], samplerate, window_s=window_s)
    if len(values) < 30:
        raise HTTPException(
            status_code=502,
            detail=f"nagranie dalo tylko {len(values)} okien -- potrzeba co najmniej 30.",
        )

    device_name = f"audio#{device}"
    try:
        device_name = _sd.query_devices(device)["name"]
    except Exception:
        pass  # nazwa opcjonalna -- brak nie powinien wywalic calego wyniku

    try:
        return compute_run_from_device_samples(
            values, port_label=device_name, device_kind="mikrofon, dominujaca czestotliwosc"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
