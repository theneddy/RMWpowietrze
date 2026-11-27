"""Test wykonalności (RMW 7.216): prognoza jakości powietrza Copernicus CAMS dla Polski.

Uruchamiany ręcznie z GitHub Actions (workflow „Test CAMS"). Nic nie publikuje, nic nie zapisuje poza katalogiem
roboczym runnera. Wynik = log: opis zbioru (dozwolone pola), czas kolejki, rozmiar pliku, struktura danych,
PM10/PM2.5 dla Wrocławia i Karpacza, szacunek rozmiaru kafla JSON dla RMWpogoda.

Klucz: sekret repozytorium ADS_KEY (osobisty token z profilu Atmosphere Data Store). Skrypt go NIE wypisuje.
Dane: Copernicus Atmosphere Monitoring Service, licencja CC BY 4.0.
"""
import datetime as dt
import json
import os
import sys
import time
import zipfile

import requests

ADS = "https://ads.atmosphere.copernicus.eu/api"
ZBIOR = "cams-europe-air-quality-forecasts"
# Polska z zapasem: północ, zachód, południe, wschód (konwencja CDS „area")
OBSZAR = [55.0, 14.0, 49.0, 24.2]
PUNKTY = {"Wrocław": (51.108, 17.039), "Karpacz": (50.776, 15.756), "Kraków": (50.062, 19.937)}
GODZINY = [str(h) for h in range(0, 97)]   # 0…96 h od startu modelu (00 UTC)


def log(*a):
    print(*a, flush=True)


def opis_zbioru():
    """Publiczny opis procesu: jakie pola przyjmuje zlecenie i jakie mają wartości."""
    url = ADS + "/retrieve/v1/processes/" + ZBIOR
    try:
        r = requests.get(url, timeout=60)
        log("OPIS ZBIORU:", url, "HTTP", r.status_code, len(r.content), "B")
        j = r.json()
    except Exception as e:  # noqa: BLE001 — test ma tylko raportować
        log("OPIS ZBIORU: błąd", repr(e))
        return
    wej = j.get("inputs") or {}
    log("  pola zlecenia:", ", ".join(sorted(wej.keys())))
    for k in sorted(wej.keys()):
        s = json.dumps(wej[k], ensure_ascii=False)
        log("  •", k, "→", s[:600] + (" …" if len(s) > 600 else ""))


def zlecenie(data):
    return {
        "variable": ["particulate_matter_10um", "particulate_matter_2.5um"],
        "model": ["ensemble"],
        "level": ["0"],
        "date": [data + "/" + data],
        "type": ["forecast"],
        "time": ["00:00"],
        "leadtime_hour": GODZINY,
        "data_format": "netcdf",
        "area": OBSZAR,
    }


def pobierz():
    import cdsapi

    klucz = os.environ.get("ADS_KEY", "").strip()
    if not klucz:
        log("BŁĄD: brak sekretu ADS_KEY w repozytorium (Settings → Secrets and variables → Actions)")
        sys.exit(1)
    klient = cdsapi.Client(url=ADS, key=klucz, quiet=False, progress=False)
    dzis = dt.datetime.utcnow().date()
    for data in (dzis.isoformat(), (dzis - dt.timedelta(days=1)).isoformat()):
        z = zlecenie(data)
        log("ZLECENIE:", json.dumps({k: (v if k != "leadtime_hour" else "0…96") for k, v in z.items()}, ensure_ascii=False))
        t0 = time.time()
        try:
            plik = klient.retrieve(ZBIOR, z, "cams_" + data + ".dat")
            plik = plik if isinstance(plik, str) else "cams_" + data + ".dat"
            log("WYNIK: zlecenie na", data, "gotowe po", round(time.time() - t0), "s (kolejka + pobranie),",
                os.path.getsize(plik), "B")
            return data, plik
        except Exception as e:  # noqa: BLE001
            log("WYNIK: zlecenie na", data, "NIEUDANE po", round(time.time() - t0), "s:", repr(e)[:1500])
    log("WYNIK: oba zlecenia nieudane — koniec")
    sys.exit(1)


def otworz(plik):
    import xarray as xr

    with open(plik, "rb") as f:
        glowa = f.read(4)
    log("FORMAT pliku (pierwsze bajty):", glowa)
    if glowa[:2] == b"PK":
        with zipfile.ZipFile(plik) as z:
            nazwy = z.namelist()
            log("ZIP:", nazwy)
            z.extractall("rozpak")
        pliki = [os.path.join("rozpak", n) for n in nazwy if n.endswith(".nc")]
        return xr.merge([xr.open_dataset(p) for p in pliki])
    return xr.open_dataset(plik)


def analiza(ds):
    log("STRUKTURA:")
    log(ds)
    zmienne = [v for v in ds.data_vars if ds[v].ndim >= 2]
    lat = "latitude" if "latitude" in ds.coords else "lat"
    lon = "longitude" if "longitude" in ds.coords else "lon"
    lons = ds[lon].values
    if lons.max() > 180:  # siatka 0…360
        ds = ds.assign_coords({lon: ((ds[lon] + 180) % 360) - 180}).sortby(lon)
    log("SIATKA:", ds[lat].size, "×", ds[lon].size, "punktów; zmienne:", zmienne)
    for nazwa, (la, lo) in PUNKTY.items():
        for v in zmienne:
            s = ds[v].sel({lat: la, lon: lo}, method="nearest").squeeze()
            wart = [round(float(x)) for x in s.values.ravel()]
            log("WYNIK:", nazwa, v, "— godzin", len(wart), "· pierwsze 24 h:", wart[:24])
            dni = [max(wart[i:i + 24]) for i in range(0, len(wart), 24) if wart[i:i + 24]]
            log("        maksimum dobowe (kolejne doby od startu modelu):", dni)
    # Kafel 1°×1° wokół Wrocławia — ile waży JSON z liczbami całkowitymi (to pobierałby RMWpogoda)
    la0, lo0 = PUNKTY["Wrocław"]
    kafel = {}
    for v in zmienne:
        w = ds[v].sel({lat: slice(la0 + 0.5, la0 - 0.5) if ds[lat].values[0] > ds[lat].values[-1] else slice(la0 - 0.5, la0 + 0.5),
                       lon: slice(lo0 - 0.5, lo0 + 0.5)}).squeeze()
        kafel[v] = [[round(float(x)) for x in rz] for rz in w.values.reshape(w.shape[0], -1)]
    txt = json.dumps(kafel, separators=(",", ":"))
    log("WYNIK: kafel 1°×1° (Wrocław) jako JSON:", len(txt), "B")


def main():
    log("Start:", dt.datetime.utcnow().isoformat(), "UTC")
    opis_zbioru()
    data, plik = pobierz()
    try:
        ds = otworz(plik)
        analiza(ds)
    except Exception as e:  # noqa: BLE001
        log("WYNIK: plik pobrany, ale odczyt nieudany:", repr(e)[:1500])
        sys.exit(1)
    log("Koniec:", dt.datetime.utcnow().isoformat(), "UTC")


if __name__ == "__main__":
    main()
