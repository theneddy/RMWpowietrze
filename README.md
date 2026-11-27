# RMWpowietrze

Prognoza jakości powietrza (pył PM10 i PM2.5) dla Polski dla aplikacji Run My Way — część pogody (`RMWpogoda`).

**Jak działa (RMW 7.217):** workflow „Prognoza” codziennie (07:35 i 11:35 UTC, także ręcznie) pobiera prognozę
CAMS European air quality forecasts (model ensemble, start 00 UTC, 0–48 h), tnie siatkę 0,1° nad Polską na kafle
1° × 1° i publikuje je na gałąź `gh-pages`:

- `https://theneddy.github.io/RMWpowietrze/indeks.json` — start przebiegu, liczba godzin, czas utworzenia, lista kafli;
- `https://theneddy.github.io/RMWpowietrze/kafle/<szer>_<dł>.json` — np. `51_17` (dolny lewy róg w pełnych stopniach):
  `start` (UTC), `godz` (przesunięcia w h), `lat`/`lon` punktów, `pm10`/`pm25` — µg/m³ na godzinę, liczby
  całkowite, −1 = brak.

Odczytuje je pośrednik pogody `RMWpogoda` (repozytorium RMW). Workflow „Test CAMS” (ręczny) został jako narzędzie
diagnostyczne. Kontekst i decyzje: RMW, `docs/analiza-2026-11-26-prognoza-powietrza.md`.

**Ustawienie jednorazowe:** Settings → Pages → Source: „Deploy from a branch” → `gh-pages` / `(root)`
(gałąź powstaje przy pierwszym udanym przebiegu „Prognoza”).

Repozytorium jest publiczne celowo: wynik to dane publiczne, a GitHub Pages na planie Free działa tylko dla
repozytoriów publicznych. Nie trafiają tu żadne dane zawodników. Jedyny sekret, klucz `ADS_KEY` do Copernicus
Atmosphere Data Store, siedzi w sekretach repozytorium i nie jest wypisywany w logach.

## Źródło danych

Generated using Copernicus Atmosphere Monitoring Service information [2026].
Dane: CAMS European air quality forecasts, licencja CC BY 4.0. Neither the European Commission nor ECMWF is
responsible for any use that may be made of the information it contains.
