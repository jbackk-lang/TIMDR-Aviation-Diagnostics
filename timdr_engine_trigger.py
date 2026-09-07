# ============================================
# TIMDR Engine Trigger Module
# ============================================
#
# ROLA: czujnik naruszeń integralności sygnału silnika — NIE model, NIE
# walidator. Nie liczy własnej detekcji: dispatcher nad TIMDR_EarthquakeCore
# (przeniesiony 1:1 z TIMDR-Earthquake-Core, 68/68 testów, sta_lta/
# trigger_onset zweryfikowane co do bitu z ObsPy — patrz timdr_core.py).
# Jedyna robota tego pliku: zapytać hybrid_trigger()/classify_anomalies()
# i powiedzieć, KTÓRY typ zdarzenia odpalił się i GDZIE.
#
# Priorytet: CONFIRMED (STA/LTA potwierdzone przez twist ORAZ anomaly —
# trzy niezależne detektory się zgadzają, wymaga nsta/nlta) > DROPOUT
# (uszkodzona telemetria — czujnik utknął, priorytet przed próbą
# interpretacji martwych danych jako realnego sygnału) > LEVEL_SHIFT
# (step/drift — trwała zmiana poziomu) > TRANSIENT (impuls/spike —
# przemijające, wraca do poprzedniego poziomu) > NONE. Ta sama zasada co
# w TIMDR-Security-Module: silniejszy/bardziej ugruntowany dowód wygrywa
# niezależnie od tego, co pojawiło się chronologicznie pierwsze —
# klasyfikacja PO TYPIE zdarzenia (nie po `start`), świadomie.
#
# nsta/nlta są opcjonalne: bez nich CONFIRMED nigdy się nie sprawdza — nie
# ma jak dobrać rozmiar okna STA/LTA bez znajomości konkretnego sygnału
# (hybrid_trigger() sam to zaznacza jako próg do kalibracji, nie
# uniwersalną wartość).

from enum import Enum
from timdr_core import TIMDR_EarthquakeCore


class EngineTriggerType(Enum):
    CONFIRMED = "confirmed_event"
    DROPOUT = "sensor_dropout"
    LEVEL_SHIFT = "level_shift"
    TRANSIENT = "transient"
    NONE = "none"


class EngineTriggerResult:
    def __init__(self, triggered=False, trigger_type=EngineTriggerType.NONE,
                 location=None, message=""):
        self.triggered = triggered
        self.trigger_type = trigger_type
        self.location = location
        self.message = message

    def as_dict(self):
        return {
            "triggered": self.triggered,
            "type": self.trigger_type.value,
            "location": self.location,
            "message": self.message,
        }


class TIMDREngineTrigger:
    """
    Dispatcher nad TIMDR_EarthquakeCore. `t`: numer cyklu (lub czas), `s`:
    odczyt czujnika. Progi (anomaly_factor, twist_threshold, sta_lta_thr_*)
    to punkty startowe do dostrojenia, nie wartości uniwersalne — ta sama
    uwaga co przy każdym innym progu w tym ekosystemie.
    """

    def __init__(self, k_neighbors=8, anomaly_factor=3.0, twist_threshold=0.4):
        self.core = TIMDR_EarthquakeCore(k_neighbors=k_neighbors)
        self.anomaly_factor = anomaly_factor
        self.twist_threshold = twist_threshold
        self.last_result = EngineTriggerResult()

    def analyze(self, t, s, nsta=None, nlta=None,
                sta_lta_thr_on=1.5, sta_lta_thr_off=0.5, tolerance=5):
        if nsta is not None and nlta is not None:
            confirmed, _rejected = self.core.hybrid_trigger(
                t, s, nsta, nlta,
                twist_threshold=self.twist_threshold,
                anomaly_factor=self.anomaly_factor,
                sta_lta_thr_on=sta_lta_thr_on, sta_lta_thr_off=sta_lta_thr_off,
                tolerance=tolerance,
            )
            if len(confirmed):
                start, _end = confirmed[0]
                return self._set_result(
                    True, EngineTriggerType.CONFIRMED, int(start),
                    "STA/LTA event confirmed by both twist and anomaly detectors."
                )

        events = self.core.classify_anomalies(t, s, factor=self.anomaly_factor)
        if not events:
            return self._set_result(False, EngineTriggerType.NONE, None,
                                    "No signal integrity trigger detected.")

        dropouts = [e for e in events if e["type"] == "dropout"]
        if dropouts:
            e = dropouts[0]
            return self._set_result(
                True, EngineTriggerType.DROPOUT, e["start"],
                f"Stuck sensor/telemetry: {e['duration']} near-constant samples."
            )

        shifts = [e for e in events if e["type"] in ("step", "drift")]
        if shifts:
            e = shifts[0]
            return self._set_result(
                True, EngineTriggerType.LEVEL_SHIFT, e["start"],
                f"Persistent {e['type']} level shift ({e['level_shift']:.3g})."
            )

        transients = [e for e in events if e["type"] in ("impuls", "spike")]
        if transients:
            e = transients[0]
            return self._set_result(
                True, EngineTriggerType.TRANSIENT, e["start"],
                f"Brief {e['type']} that reverted to the prior level."
            )

        # classify_anomalies() ma tylko powyzsze 5 typow - to nie powinno
        # byc osiagalne, ale nie zgadujemy w razie przyszlej zmiany API.
        return self._set_result(False, EngineTriggerType.NONE, None,
                                "Unrecognized event shape from classify_anomalies().")

    def _set_result(self, triggered, trigger_type, location, message):
        self.last_result = EngineTriggerResult(triggered, trigger_type, location, message)
        return self.last_result

    def get_last(self):
        return self.last_result
