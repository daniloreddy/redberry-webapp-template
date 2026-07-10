# App Skeleton

Base riusabile per applicazioni web Python: FastAPI/uvicorn + dashboard NiceGUI,
auth cookie/JWT, config runtime hot-reloadable, rate limiting, metriche persistite
su SQLite. Non è un prodotto — è il punto di partenza per un progetto nuovo.

Le funzioni condivise (auth, config, env resolution, redazione log, timezone,
metriche) vengono da [`redberry-webkit`](https://github.com/daniloreddy/redberry-webkit),
pacchetto pip. Questo repo aggiunge solo il **cablaggio applicativo** attorno a
quel pacchetto: `main.py`, routing, pagine NiceGUI, Docker, script.

## Funzionalità incluse

- **Auth dashboard** (`/ui/*`) — cookie/JWT, login/logout, rate limit anti-bruteforce.
- **Config runtime** (`/ui/config`) — switch/campi legati a `.env`, hot-reload senza restart.
- **Rate limiting** (`slowapi`) su endpoint API, limite configurabile a runtime.
- **Metriche** — storico richieste persistito su SQLite (`app/metrics.py`), mostrato in dashboard.
- **Docker** — due compose file (prod/dev), bind-mount dati, workflow GHCR pronto.

## Come partire da questo scaffold per un progetto nuovo

Questo repo è un template [Copier](https://copier.readthedocs.io/) — non si copia
a mano. Copier tiene traccia (in `.copier-answers.yml`, generato nel progetto
derivato) di quale versione dello scaffold è stata usata, così un fix successivo
qui può essere riapplicato ai progetti già creati (`copier update`), invece di
restare bloccato alla copia iniziale.

1. Installa Copier una volta sola (tool CLI, non dipendenza del progetto):
   ```bash
   pipx install copier   # o: pip install --user copier
   ```
2. Genera il nuovo progetto:
   ```bash
   copier copy https://github.com/daniloreddy/redberry-app-skeleton.git percorso/nuovo-progetto
   # oppure, da un checkout locale dello scaffold:
   copier copy C:/redberry/src/python/redberry-app-skeleton percorso/nuovo-progetto
   ```
   Copier chiede `app_name` (es. "Mail Manager"), `app_slug` (default derivato
   automaticamente, usato per cookie/Docker) e `github_owner`. I valori sostituiscono
   tutti i riferimenti hardcoded (`APP_NAME`, `cookie_name`, nome servizio/immagine
   Docker, `FastAPI(title=...)`, `static/login.html`) — nessun rename manuale.
3. `cd percorso/nuovo-progetto && git init` (il template non include `.git`).
4. Cancella `app/libs/example.py` (e il suo test) e aggiungi lì la logica vera del
   progetto — moduli puri, senza import FastAPI/NiceGUI, testabili senza `TestClient`.
5. Estendi `app/config.py`: aggiungi le chiavi runtime-editable specifiche del
   progetto a `_DEFAULTS`/`_SECRET_KEYS` (nessuna sottoclasse necessaria — vedi
   il commento nel file). Aggiungi i campi corrispondenti nella pagina Config
   (`app/ui/pages.py`, `config_page()`), seguendo lo stesso pattern già presente.
6. Sostituisci `GET /api/v1/example` in `app/main.py` con gli endpoint reali,
   mantenendo il pattern `@limiter.limit(...)` + `metrics.record(...)`.
7. Aggiorna `requirements.txt` con le dipendenze specifiche del progetto.
8. Copia `.env.example` in `.env`, imposta la password: `python scripts/set_password.py`.

### Aggiornare un progetto derivato quando lo scaffold cambia

Dalla cartella del progetto derivato (richiede `.copier-answers.yml` committato,
generato automaticamente al passo 2):

```bash
copier update
```

Copier calcola il diff tra la versione dello scaffold usata alla creazione e
quella corrente, e lo riapplica al progetto — come un merge git. Conflitti su
file personalizzati (es. `app/main.py` se hai aggiunto endpoint) vanno risolti
a mano, marcati `.rej`/marker di conflitto nel file, stesso flusso di un merge.

## Avvio rapido (locale)

```bash
# Windows
scripts\run.bat --dev

# Linux / Mac
scripts/run.sh --dev
```

Il primo avvio crea il virtual environment e installa le dipendenze. Copia
`.env.example` in `.env` prima del primo avvio e imposta la password:

```bash
python scripts/set_password.py
```

Server su `http://127.0.0.1:8000`. Dashboard su `http://127.0.0.1:8000/ui` (richiede login).

## Configurazione (`.env`)

Vedi `.env.example` per l'elenco completo. Variabili principali:

| Variabile | Default | Note |
|---|---|---|
| `HOST` | `127.0.0.1` | Bind locale. |
| `PORT` | `8000` | |
| `DEV` | `false` | `true` abilita `--reload` uvicorn e riattiva `/docs`/`/redoc`. |
| `TZ` | `UTC` | Fuso orario IANA per i timestamp mostrati in dashboard. |
| `TRUSTED_PROXIES` | `127.0.0.1` | IP dei reverse proxy fidati per risolvere l'IP client reale. |
| `AUTH_SECURE_COOKIE` | `0` | `1` forza il flag `Secure` sul cookie anche senza `X-Forwarded-Proto: https`. |
| `API_TOKENS` | *(vuoto)* | Bearer token comma-separated per eventuali endpoint API fuori da `/ui`. |
| `RATE_LIMIT` | `20/minute` | Limite (sintassi slowapi) sugli endpoint API — hot-reload, modificabile da `/ui/config`. |
| `REFRESH_ENABLED` / `REFRESH_INTERVAL` | `true` / `5` | Auto-refresh dashboard — hot-reload, modificabile da `/ui/config`. |
| `NICEGUI_STORAGE_PATH` | *(vuoto)* | Solo Docker: `/app/data/.nicegui` per persistere il tema dark/light tra restart. |

## Docker

```bash
# sviluppo (build locale)
docker compose -f docker-compose-dev.yml up --build

# produzione (immagine da GHCR)
docker compose up -d
```

Di default `docker-compose.yml` pubblica solo su `127.0.0.1`; imposta
`HOST=0.0.0.0` in `.env` per esporre su LAN/reverse proxy.

## Sviluppo

```bash
# Windows
scripts\checks.bat

# Linux / Mac
scripts/checks.sh
```

Esegue `ruff check`, `mypy app` (strict) e `pytest` in sequenza.

## Struttura del progetto

```
app/
├── main.py         # FastAPI + lifespan (config reload, auth purge, metrics init) + auth gate +
│                   # rate limiting + /health + mount NiceGUI + esempio endpoint
├── config.py       # ConfigManager (redberry_webkit) con i default runtime-editable dello scaffold
├── metrics.py      # MetricsStore (redberry_webkit) legato a data/metrics.db
├── libs/           # logica pura specifica del progetto — example.py è un placeholder da sostituire
└── ui/
    ├── router.py   # /login /auth/login /auth/logout (AuthManager)
    └── pages.py    # dashboard (metriche + storico) + pagina Config
static/login.html   # pagina di login self-contained
scripts/            # run/checks (bat+sh), set_password.py
data/               # auth.json, metrics.db, logs/ — gitignored
```

## Licenza

Uso interno / non specificata.
