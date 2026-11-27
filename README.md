# RMWpowietrze

Prognoza jakości powietrza (pył PM10 i PM2.5) dla Polski dla aplikacji Run My Way — część pogody (`RMWpogoda`).

**Stan: test wykonalności.** Workflow „Test CAMS” (uruchamiany ręcznie) sprawdza, czy prognozę da się pobrać
i odczytać. Nic jeszcze nie jest publikowane. Kontekst i decyzje: repozytorium RMW,
`docs/analiza-2026-11-26-prognoza-powietrza.md`.

Repozytorium jest publiczne celowo: wynik to dane publiczne, a GitHub Pages na planie Free działa tylko dla
repozytoriów publicznych. Nie trafiają tu żadne dane zawodników. Jedyny sekret, klucz `ADS_KEY` do Copernicus
Atmosphere Data Store, siedzi w sekretach repozytorium i nie jest wypisywany w logach.

## Źródło danych

Generated using Copernicus Atmosphere Monitoring Service information [2026].
Dane: CAMS European air quality forecasts, licencja CC BY 4.0. Neither the European Commission nor ECMWF is
responsible for any use that may be made of the information it contains.
