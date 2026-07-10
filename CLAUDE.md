# App Skeleton

Scaffold riusabile, non un prodotto. Punto di partenza per nuovi progetti
FastAPI + NiceGUI — vedi `README.md` per la checklist di derivazione.

## Dipendenze condivise

`env_resolver`, `auth`, `config`, `logging_utils`, `timezone_utils`, `metrics`
vivono in [`redberry-webkit`](https://github.com/daniloreddy/redberry-webkit),
pacchetto pip condiviso. Pin in `requirements.txt`:
`redberry-webkit @ git+https://github.com/daniloreddy/redberry-webkit.git@vX.Y.Z`.

Bugfix/feature nel pacchetto → nuovo tag semver nel repo `redberry-webkit` →
bump manuale del pin qui. Prima di reimplementare uno di questi moduli da zero,
controllare se `redberry-webkit` lo copre già.

## Cosa va in redberry-webkit vs cosa resta qui

- **redberry-webkit**: logica pura, nessun import FastAPI/NiceGUI, identica a
  prescindere dal progetto (auth, config, metriche, credential redaction, tz).
- **Questo scaffold**: cablaggio applicativo — routing, pagine, wiring di
  `main.py`, Docker, script. Ogni progetto derivato lo personalizza.

## Estensione di `app/config.py`

`ConfigManager` (redberry-webkit) accetta `defaults`/`secret_keys` come dict
nel costruttore — nessuna sottoclasse necessaria. Un progetto derivato estende
i due dict in `app/config.py` prima di costruire `config`, poi aggiunge i campi
corrispondenti nella pagina Config (`app/ui/pages.py`).

## Vincoli d'esecuzione

- **`workers=1` obbligatorio**: `ConfigManager`, `AuthManager` (rate-limit dict
  in-process), `MetricsStore`/SQLite sono stato non condiviso tra worker.
- **`HOST` default `127.0.0.1`**: non esporre oltre localhost senza aver
  valutato `API_TOKENS`/rate limiting per gli endpoint API del progetto reale.

## Test

`tests/test_main.py` copre health, auth gate, login flow, docs disabilitati
fuori da `DEV`, rate limiting. `tests/test_libs_example.py` è un placeholder
da sostituire insieme a `app/libs/example.py`.
