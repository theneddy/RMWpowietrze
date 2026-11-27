"""Prognoza jakości powietrza (PM10, PM2.5) dla Polski → kafle JSON dla RMWpogoda (RMW 7.217).

Uruchamiany przez workflow „Prognoza" (codziennie i ręcznie). Pobiera z Copernicus Atmosphere Data Store prognozę
CAMS European air quality forecasts (model ensemble, start 00 UTC, 0–48 h — decyzja Marka 27.11: 48 h wystarczy),
tnie siatkę nad Polską na kafle 1° × 1° i zapisuje do katalogu `publikacja/` (workflow publikuje go na gh-pages).

Format kafla `kafle/<szer>_<dł>.json` (szer/dł = dolny lewy róg w pełnych stopniach, np. 51_17):
  {"v":1, "start":"2026-11-27T00:00:00Z", "godz":[0..48], "lat":[...], "lon":[...],
   "pm10":[[..godziny..] na punkt], "pm25":[[..]]}  — µg/m³ jako liczby całkowite, -1 = brak wartości.
Godzina k = start + k h (UTC). Punkty: środki oczek siatki 0,1°.

Klucz: sekret ADS_KEY (nie jest wypisywany). Dane: Copernicus, licencja CC BY 4.0.
"""
import datetime as dt
import json
import math
import os
import shutil
import sys
import time
import zipfile

ADS = "https://ads.atmosphere.copernicus.eu/api"
ZBIOR = "cams-europe-air-quality-forecasts"
OBSZAR = [55.0, 14.0, 49.0, 24.2]           # północ, zachód, południe, wschód
GODZINY = [str(h) for h in range(0, 49)]    # 0–48 h
WYJ = "publikacja"
ATRYBUCJA = "Generated using Copernicus Atmosphere Monitoring Service information {rok}. Neither the European Commission nor ECMWF is responsible for any use that may be made of the information it contains."


def log(*a):
    print(*a, flush=True)


def zlecenie(data):
    return {
        "variable": ["particulate_matter_10um", "particulate_matter_2.5um"],
        "model": ["ensemble"], "level": ["0"], "date": [data + "/" + data], "type": ["forecast"],
        "time": ["00:00"], "leadtime_hour": GODZINY, "data_format": "netcdf_zip", "area": OBSZAR,
    }


def pobierz():
    """Dzisiejszy przebieg (00 UTC); gdy jeszcze go nie ma — wczorajszy. → (data, plik)."""
    import cdsapi

    klucz = os.environ.get("ADS_KEY", "").strip()
    if not klucz:
        log("BŁĄD: brak sekretu ADS_KEY")
        sys.exit(1)
    klient = cdsapi.Client(url=ADS, key=klucz, quiet=True, progress=False)
    dzis = dt.datetime.now(dt.timezone.utc).date()
    for data in (dzis.isoformat(), (dzis - dt.timedelta(days=1)).isoformat()):
        t0 = time.time()
        try:
            cel = "cams_" + data + ".zip"
            plik = klient.retrieve(ZBIOR, zlecenie(data), cel)
            plik = plik if isinstance(plik, str) else cel
            log("Pobrano przebieg", data, "w", round(time.time() - t0), "s,", os.path.getsize(plik), "B")
            return data, plik
        except Exception as e:  # noqa: BLE001
            log("Przebieg", data, "niedostępny po", round(time.time() - t0), "s:", repr(e)[:600])
    log("BŁĄD: brak przebiegu z dziś i z wczoraj")
    sys.exit(1)


def otworz(plik):
    import xarray as xr

    with open(plik, "rb") as f:
        zip_ = f.read(2) == b"PK"
    if not zip_:
        return xr.open_dataset(plik)
    if os.path.isdir("rozpak"):
        shutil.rmtree("rozpak")
    with zipfile.ZipFile(plik) as z:
        z.extractall("rozpak")
        nazwy = sorted(n for n in z.namelist() if n.endswith(".nc"))
    zb = [xr.open_dataset(os.path.join("rozpak", n)) for n in nazwy]
    return zb[0] if len(zb) == 1 else xr.combine_by_coords(zb, combine_attrs="drop_conflicts")


def kafle(ds, data):
    """Siatka → {nazwa: kafel}. Wymiary pól: (time, [level,] lat, lon)."""
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    if float(ds[lon].max()) > 180:
        ds = ds.assign_coords({lon: ((ds[lon] + 180) % 360) - 180}).sortby(lon)
    pola = {"pm10": "pm10_conc", "pm25": "pm2p5_conc"}
    for k, v in pola.items():
        if v not in ds.data_vars:
            raise ValueError("brak zmiennej " + v + " w pliku; są: " + ", ".join(ds.data_vars))
    godz = [int(round(float(x))) for x in ds["time"].values]
    lats = [round(float(x), 2) for x in ds[lat].values]
    lons = [round(float(x), 2) for x in ds[lon].values]
    tabl = {}
    for k, v in pola.items():
        a = ds[v]
        if "level" in a.dims:
            a = a.isel(level=0)
        a = a.transpose("time", lat, lon).values  # [czas][szer][dł]
        tabl[k] = a
    start = data + "T00:00:00Z"
    wyn = {}
    for i, la in enumerate(lats):
        for j, lo in enumerate(lons):
            nazwa = "%d_%d" % (math.floor(la), math.floor(lo))
            kf = wyn.setdefault(nazwa, {"v": 1, "start": start, "godz": godz, "lat": [], "lon": [], "pm10": [], "pm25": []})
            kf["lat"].append(la)
            kf["lon"].append(lo)
            for k in pola:
                kol = tabl[k][:, i, j]
                kf[k].append([-1 if (x != x) else int(round(float(x))) for x in kol])  # x != x → NaN
    return wyn


def zapisz(wyn, data):
    if os.path.isdir(WYJ):
        shutil.rmtree(WYJ)
    os.makedirs(os.path.join(WYJ, "kafle"))
    rozm = []
    for nazwa, kf in sorted(wyn.items()):
        txt = json.dumps(kf, separators=(",", ":"))
        rozm.append(len(txt))
        with open(os.path.join(WYJ, "kafle", nazwa + ".json"), "w", encoding="utf-8") as f:
            f.write(txt)
    teraz = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    indeks = {"v": 1, "start": data + "T00:00:00Z", "godzin": len(next(iter(wyn.values()))["godz"]), "utworzono": teraz,
              "zrodlo": "CAMS European air quality forecasts, model ensemble", "licencja": "CC BY 4.0",
              "atrybucja": ATRYBUCJA.format(rok=data[:4]), "kafle": sorted(wyn.keys())}
    with open(os.path.join(WYJ, "indeks.json"), "w", encoding="utf-8") as f:
        json.dump(indeks, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(WYJ, ".nojekyll"), "w") as f:
        f.write("")
    with open(os.path.join(WYJ, "index.html"), "w", encoding="utf-8") as f:
        f.write("<!doctype html><meta charset=utf-8><title>RMWpowietrze</title><p>Prognoza PM10/PM2.5 dla Polski "
                "(dane dla aplikacji Run My Way): <a href=indeks.json>indeks.json</a>.</p><p>" + indeks["atrybucja"] + "</p>")
    log("Kafli:", len(wyn), "· rozmiar kafla min/maks:", min(rozm), "/", max(rozm), "B · start", indeks["start"],
        "· godzin", indeks["godzin"])


def main():
    data, plik = pobierz()
    ds = otworz(plik)
    wyn = kafle(ds, data)
    zapisz(wyn, data)


if __name__ == "__main__":
    main()
