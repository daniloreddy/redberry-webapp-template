# Redberry Webapp Template

Scaffold riusabile, non un prodotto. Punto di partenza per nuovi progetti
FastAPI + NiceGUI — vedi `README.md` per la checklist di derivazione.

## Template Copier — questo repo non è direttamente eseguibile

Da quando è stato convertito in template [Copier](https://copier.readthedocs.io/),
i file che contengono placeholder (`app/main.py.jinja`, `app/ui/router.py.jinja`,
`app/ui/pages.py.jinja`, `static/login.html.jinja`, `docker-compose*.yml.jinja`)
esistono solo con suffisso `.jinja` nel sorgente — Copier lo strip al momento
della generazione. Questo significa che **`python -m app.main`, `pytest`, `mypy
app` NON funzionano lanciati direttamente in questo repo** (i file `.py` veri
non esistono finché non generi un'istanza).

**Per modificare/validare lo scaffold**: genera un'istanza di prova con Copier e
lavora/testa lì, poi riporta le modifiche verificate nei file `.jinja` sorgente:

```bash
copier copy . /tmp/skeleton-smoke-test --data app_name="Smoke Test" --defaults
cd /tmp/skeleton-smoke-test && scripts/checks.bat   # o checks.sh
```

**Attenzione — modifiche non committate**: `copier copy .` con una source path che è
un repo git genera dall'ultimo commit (`HEAD`), **non** dal working tree — modifiche
non ancora committate ai `.jinja` non compaiono nell'istanza generata, senza nessun
avviso. Per validare modifiche non committate, copiare prima i file tracked in una
directory temporanea senza `.git` e puntare Copier lì:

```bash
mkdir -p /tmp/webapp-template-src && cp -r --parents $(git ls-files) /tmp/webapp-template-src
# poi sovrascrivere i .jinja modificati non ancora committati, es.:
cp app/main.py.jinja /tmp/webapp-template-src/app/main.py.jinja
copier copy /tmp/webapp-template-src /tmp/skeleton-smoke-test --data app_name="Smoke Test" --defaults
```

`.github/workflows/docker-publish.yml` è l'unico file copiato 1:1 senza rendering
(usa `${{ }}` per le espressioni GitHub Actions, che collide con la sintassi
Jinja di default — per questo il meccanismo di rendering è opt-in per-file via
suffisso `.jinja`, non globale).

## Dipendenze condivise

`env_resolver`, `auth`, `config`, `logging_utils`, `timezone_utils`, `metrics`
vivono in [`redberry-webkit`](https://github.com/daniloreddy/redberry-webkit),
pacchetto pip condiviso. Pin in `requirements.txt`:
`redberry-webkit @ git+https://github.com/daniloreddy/redberry-webkit.git@vX.Y.Z`.

Bugfix/feature nel pacchetto → nuovo tag semver nel repo `redberry-webkit` →
bump manuale del pin qui.

**Il pin è su un tag Git (`@vX.Y.Z`), non su uno SHA — rischio accettato,
non un oversight.** Un tag è mutabile: chi ha accesso push a `redberry-webkit`
può farlo puntare altrove senza che questo pin cambi. Con `redberry-webkit`
pubblico e a controllo esclusivo del proprietario, l'unico scenario in cui
questo importa è un account GitHub compromesso — a quel punto il problema è
comunque più ampio del pin. Passare a uno SHA di commit eliminerebbe il
rischio ma renderebbe ogni bump manuale meno leggibile (uno SHA non comunica
la versione) per un guadagno marginale in questo contesto single-owner —
deciso 2026-09-21, non da rivedere senza un cambio reale nel modello di minaccia
(es. accesso push condiviso con terzi).

Prima di reimplementare uno di questi moduli da zero,
controllare se `redberry-webkit` lo copre già.

`AuthManager.verify_password()` (redberry-webkit ≥v0.2.0, scrypt N=131072) è
sincrona e costa ~150-250ms/~128MB per chiamata — in `app/ui/router.py.jinja`
va sempre invocata via `asyncio.to_thread(...)`, mai inline nell'handler async
`/auth/login` (bloccherebbe l'event loop). La chiamata è inoltre avvolta in
`_login_semaphore` (`_LOGIN_MAX_CONCURRENT = 4`) + `asyncio.wait_for(...,
timeout=_LOGIN_VERIFY_TIMEOUT_S)` → 503 su timeout: senza cap, un burst di
richieste non autenticate a `/auth/login` potrebbe spingere N × ~128MB di RAM
in parallelo (nessun rate-limit slowapi su questa rotta, per design — vedi
`is_global_limited()`/SEC-02 sopra). Pattern già cablato nel template —
mantenerlo in ogni personalizzazione del login flow.

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
fuori da `DEV`, rate limiting, il cap di concorrenza sul login
(`test_login_semaphore_caps_concurrent_verify`, verifica che
`_login_semaphore` limiti davvero le verifiche scrypt in-flight) e il rigetto
di un Bearer token non-ASCII sull'endpoint API di esempio
(`test_example_endpoint_rejects_non_ascii_bearer_token_with_401`, copre il
`TypeError` di `hmac.compare_digest` su input non-ASCII gestito da
`redberry_webkit.auth.verify_api_token`). `tests/test_libs_example.py` è un
placeholder da sostituire insieme a `app/libs/example.py`.

## Strumenti di manutenzione dello scaffold (non per i progetti derivati)

Due script vivono solo in questo repo template, mai copiati in un progetto
derivato (`align_to_template.py` è nell'`EXCLUDE_DIRS`/logica propria, non un
file "owned" da Copier):

- **`tools/check_drift.py`** — `copier update` segnala solo lo scostamento
  del commit pinnato in `.copier-answers.yml`, non verifica che i file
  pensati per restare "copiati verbatim" (`static/login.html`, e in generale
  quanto documentato come reference implementation in fastapi-auth.md/
  uvicorn.md) siano ancora identici al render corrente del template. Uno
  scaffold derivato può riscrivere uno di questi file a mano e `copier
  update` fa comunque un merge a 3 vie attorno alla modifica senza mai
  segnalare la divergenza. Lo script rirenderizza il template con le
  `.copier-answers.yml` di ogni progetto sibling (sotto la stessa
  `projects_root`, default la directory padre del template) e confronta
  byte per byte. Uso: `python tools/check_drift.py [projects_root]
  [path...]`.
- **`scripts/align_to_template.py`** — genera uno skeleton fresh da Copier e
  confronta ricorsivamente ogni file con un progetto target esistente,
  producendo un report a 5 sezioni (file owned divergenti da sostituire
  integralmente, file comuni non-owned con divergenza attesa, file solo nel
  progetto, file solo nello skeleton, conteggio identici). `TEMPLATE_OWNED_FILES`
  nello script è la lista dei file che devono restare byte-identici dopo un
  allineamento — qualunque divergenza lì è un bug dell'allineamento, non una
  personalizzazione legittima. Uso: `python scripts/align_to_template.py
  <path-progetto> --app-name "Nome progetto" [--report out.md]`.
