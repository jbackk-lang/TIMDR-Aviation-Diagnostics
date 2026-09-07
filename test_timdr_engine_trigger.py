"""
test_timdr_engine_trigger.py — testy timdr_engine_trigger.py.

Ten repo (kopia 1:1 TIMDR_EarthquakeCore, 68/68 testow w zrodle, sta_lta
zweryfikowane co do bitu z ObsPy) nie mial wczesniej ZADNEGO wlasnego
testu jednostkowego dla timdr_core.py - jedynym plikiem byl
test_engine_degradation.py, ktory jest skryptem demonstracyjnym na
zewnetrznych danych NASA C-MAPSS, nie pytest-em. Ponizsze testy dotycza
WYLACZNIE nowego dispatchera (timdr_engine_trigger.py) - ufamy juz
przetestowanym flow()/anomalies()/classify_anomalies()/hybrid_trigger() z
timdr_core.py (nie re-weryfikujemy ich wewnetrznej matematyki tutaj, to
nie jest robota tego pliku), sprawdzamy tylko, czy dispatcher poprawnie
je woła i mapuje wynik na wlasciwy typ.

Sygnaly testowe skonstruowane recznie tak, zeby kategoria byla
jednoznaczna z konstrukcji (dropout: dlugi biala run o kroku ~0 miedzy
sasiadami; transient: pojedynczy medianowo-odporny wyrzut wsrod
jednorodnego szumu; level_shift: trwala zmiana poziomu bez powrotu).
Detekcja dropout_runs w classify_anomalies() liczona jest WPROST z
surowych roznic s[i+1]-s[i], niezaleznie od TRM/anomalies() - dlatego
test_dropout_detected jest w pelni odtwarzalny recznie (bez potrzeby
liczenia LSQ/median po najblizszych sasiadach po czasie).
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from timdr_engine_trigger import TIMDREngineTrigger, EngineTriggerType


def _t(n):
    return list(range(n))


def test_dropout_detected():
    """
    Krok miedzy sasiadami w indeksach 8-14 (7 probek, wartosc stala 15.0)
    jest DOKLADNIE 0 - typical_diff (mediana |diff| calego sygnalu) tutaj
    to 0.2 (patrz rozklad diffow w komentarzu ponizej), wiec
    dropout_eps=0.05*0.2=0.01. Krok 0 <= 0.01 -> caly 7-probkowy plaski
    fragment to jeden dropout run (>= min_dropout_len=5). Poza tym
    fragmentem wszystkie kroki to 0.2-0.6, wiec run nie rozciaga sie dalej
    (przejscia do/z plateau to skoki 5.0/4.9).
    """
    s = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0,   # 0-7: szum
         15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0,       # 8-14: dropout
         10.1, 9.9, 10.2, 9.8, 10.0]                      # 15-19: szum
    trigger = TIMDREngineTrigger()
    result = trigger.analyze(_t(20), s)
    assert result.triggered is True
    assert result.trigger_type == EngineTriggerType.DROPOUT
    assert result.location == 8


def test_transient_detected():
    """
    Pojedynczy wyrzut 50.0 wsrod jednorodnego szumu ~10 (reszta wartosci
    nigdy sie nie powtarza identycznie, wiec zaden dropout run nie
    powstaje). TRM (mediana 8 najblizszych sasiadow PO CZASIE) dla
    indeksu 10 bierze okno [6:13] (recznie wyprowadzone z
    _nearest_k_bounds dla rownomiernego t): wartosci
    [9.7,10.0,10.1,9.9,50.0,10.0,10.2,9.8], mediana=10.0 (jeden wyrzut
    wsrod 8 wartosci nie rusza mediany) -> residuum w punkcie 10 = 40,
    o rzad wielkosci wieksze niz jakikolwiek szum lokalny gdzie indziej
    -> jednoznacznie zlapane przez próg factor*MAD. dur=1, before≈after≈10
    (nie ma trwalej zmiany poziomu) -> reverts=True -> "impuls" -> TRANSIENT.
    """
    s = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9,
         50.0,
         10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1]
    trigger = TIMDREngineTrigger()
    result = trigger.analyze(_t(20), s)
    assert result.triggered is True
    assert result.trigger_type == EngineTriggerType.TRANSIENT
    assert result.location == 10


def test_level_shift_detected():
    """
    Poziom trwale przesuwa sie z ~10 na ~20 w polowie sygnalu i NIE
    wraca - anomalie() zlapie okolice granicy (residua wobec lokalnej
    mediany TRM, ktora w oknie obejmujacym granice jest "rozdarta"
    miedzy oba poziomy), a poniewaz before≈10 i after≈20 nie miesci sie
    w revert_tol -> "step"/"drift", nie "impuls"/"spike". Dokladny
    pojedynczy indeks lokalizacji zalezy od arytmetyki mediany w oknie
    najblizszych sasiadow (nie liczonej tu co do cyfry) - sprawdzamy
    tylko kategorie i przyblizone polozenie wokol granicy (idx 9/10).
    """
    s = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9,
         20.0, 20.2, 19.8, 20.1, 19.9, 20.3, 19.7, 20.0, 20.1, 19.9]
    trigger = TIMDREngineTrigger()
    result = trigger.analyze(_t(20), s)
    assert result.triggered is True
    assert result.trigger_type == EngineTriggerType.LEVEL_SHIFT
    assert result.location is not None
    assert 7 <= result.location <= 12


def test_dropout_ma_pierwszenstwo_przed_transient():
    """
    Ten sam dropout run co w test_dropout_detected, PLUS wczesniejszy
    (chronologicznie) wyrzut w indeksie 2. Priorytet dispatchera jest PO
    TYPIE zdarzenia, nie po czasie wystapienia (ta sama zasada co w
    TIMDR-Security-Module) - to gwarancja na poziomie kodu dispatchera
    (sprawdza liste `dropouts` przed czymkolwiek innym i zwraca od razu,
    jesli niepusta), wiec ten test nie zalezy od tego, czy wyrzut w
    indeksie 2 w ogole zostanie osobno wykryty przez anomalies().
    """
    s = [10.0, 10.2,
         50.0,
         9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1,
         15.0, 15.0, 15.0, 15.0, 15.0, 15.0, 15.0,
         10.0, 9.9, 10.2]
    trigger = TIMDREngineTrigger()
    result = trigger.analyze(_t(20), s)
    assert result.triggered is True
    assert result.trigger_type == EngineTriggerType.DROPOUT
    assert result.location == 10


def test_brak_triggera_na_czystym_sygnale_takze_ze_sciezka_confirmed():
    """
    Jednorodny szum bez zadnej anomalii/dropoutu/skoku. Z nsta/nlta
    podanymi, sciezka hybrid_trigger() jest realnie wywolywana (nie
    pomijana) - energia sygnalu (s^2) jest w miare stala w calym oknie,
    wiec stosunek STA/LTA nigdy nie przekracza sta_lta_thr_on=1.5 ->
    hybrid_trigger zwraca pusta liste potwierdzonych zdarzen -> dispatcher
    spada do classify_anomalies(), ktora na tym samym jednorodnym szumie
    tez nic nie zglasza -> NONE.
    """
    s = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9,
         10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9, 10.2]
    trigger = TIMDREngineTrigger()
    result = trigger.analyze(_t(20), s, nsta=3, nlta=6)
    assert result.triggered is False
    assert result.trigger_type == EngineTriggerType.NONE


def test_get_last_zwraca_ostatni_wynik():
    trigger = TIMDREngineTrigger()
    s = [10.0, 10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9,
         10.2, 9.8, 10.1, 9.9, 10.3, 9.7, 10.0, 10.1, 9.9, 10.2]
    result = trigger.analyze(_t(20), s)
    assert trigger.get_last() is result
