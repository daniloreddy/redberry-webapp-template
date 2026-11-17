---
name: align-to-template
description: Use when asked to align, update, or migrate an existing FastAPI project to redberry-webapp-template / the latest redberry-webkit — phrases like "allinea questo progetto al template", "porta X sul template", "aggiorna il progetto al template", "allinea alle ultime versioni di webkit/template". Drives alignment via `copier update` (safe 3-way merge) plus a reviewed diff for drift the template never touched — never a blind file overwrite.
---

# Align to Template

Guida un allineamento completo di un progetto esistente a `redberry-webapp-template`
(e quindi al pin `redberry-webkit` del template).

> **Stato attuale del template**: Jinja2 + HTMX (`~/.claude/guidelines/web-py.md`), wiring comune
> (auth, login/logout, gate `/ui/*`, `/health`, `/ui/config`, logging, rate limit, security
> headers, lifespan loops, CLI) in `redberry_webkit.bootstrap` (webkit ≥ v0.7.0). Il progetto
> contiene solo `app/core.py` (`web = create_app(AppSpec(...))`), `app/main.py` (`app = web.app`
> + route del progetto), `app/__main__.py` (launcher `python -m app`), `app/libs/` (logica),
> `app/ui/{layout,pages}.py`. Un progetto con bootstrap copiato a mano (proprio `AuthManager`,
> `_auth_gate`, router di login, `uvicorn.run`) va **migrato** a quel modello: il wiring si
> cancella dal progetto, non si riallinea. Checklist: `web-py.md` §7.

**Perché questa skill esiste, e perché questa versione**: la v1 usava
`scripts/align_to_template.py` per generare una skeleton fresca e poi **sostituiva
integralmente** i file "owned dal template" (main.py, Dockerfile, docker-compose*,
script). Testata su un progetto reale (`news_scraper`), quella sostituzione ha cancellato
316 righe di route applicative da `app/main.py` e personalizzazioni Docker legittime
(`shm_size` per Playwright, volume `./debug`) — nessuno di questi file è mai puro
boilerplate in un progetto maturo. **Non farlo mai più.**

## Strumenti

- Pin webkit nuovo o feature webkit da sviluppare insieme al progetto: leggi prima
  `~/.claude/guidelines/webkit-release.md` (editable install, pin solo dopo il push del tag).

- `copier` non è nel PATH: usa `C:/redberry/src/redberry-webapp-template/venv/Scripts/copier.exe`.
- `scripts/align_to_template.py` invoca `copier` per nome: lancialo con
  `PATH="C:/redberry/src/redberry-webapp-template/venv/Scripts:$PATH"`.
- `tools/check_versions.py` (repo template): stato template/webkit di tutti i progetti
  fratelli. Usalo per capire da dove parti e per la verifica finale (`ok`).

## I due meccanismi, in ordine — non intercambiabili

1. **`copier update`** — merge a 3 vie basato su `.copier-answers.yml`: confronta
   template-alla-generazione vs template-attuale vs stato-attuale-del-progetto.
   Applica solo ciò che il template ha davvero cambiato; lascia intatto il resto.
   Dove non riesce a mergiare lascia conflict marker (`<<<<<<< before updating` /
   `>>>>>>> after updating`, file in stato `UU`) — mai silenzio. Può anche
   **cancellare** file che il template ha rimosso (es. `app/config.py`,
   `app/ui/router.py`): controlla che il codice del progetto non li importi più.
   **Meccanismo primario, sempre da provare per primo.**
2. **`scripts/align_to_template.py`** — genera una skeleton fresca e confronta con il
   progetto target. Solo **visibilità**: drift che il template non ha mai toccato, file
   mancanti/aggiuntivi. **Non scrive mai nulla da solo.**

## Input

`args`: `<path-progetto> [app_name] [app_slug]`

Se `app_name`/`app_slug` non sono forniti, leggili da `.copier-answers.yml` o da
`app/core.py` (`slug=`) / `app/ui/layout.py` (`APP_NAME`) — non inventarli.

## Passi

### 0. Sicurezza — sempre prima di toccare qualunque file

- `git status` sul progetto target. Modifiche non committate → `git stash push -u`
  (reversibile; se contiene lavoro sostanziale, segnalalo all'utente).
- Verifica che la venv funzioni (`venv/Scripts/python -c "import pydantic_core"`): una venv
  creata con un'altra versione di Python (vedi `venv/pyvenv.cfg` vs `python -V`) ha
  estensioni compilate per l'ABI sbagliato. In quel caso va ricreata (`venv` è rigenerabile).

### 1. `copier update` — passo primario

Dalla root del progetto target (richiede `.copier-answers.yml`; se manca vedi passo 5):

```
C:/redberry/src/redberry-webapp-template/venv/Scripts/copier.exe update --trust --defaults
```

> `--trust` sempre, su tutti i template (py/go/j): è la convenzione comune. Serve ai template
> con `_tasks`; sugli altri è innocuo.

> **Domande nuove + `--defaults`**: una domanda aggiunta dopo l'ultimo update del progetto
> prende in silenzio il default. Prima dell'update confronta `copier.yml` con
> `.copier-answers.yml` e passa le risposte reali con `-d chiave=valore`. Caso noto:
> `default_port` (da v0.3.10, default 8000) → `-d default_port=<porta reale del progetto>`
> (quella di `.env.example`/compose/tunnel), altrimenti Dockerfile/compose/`.env.example`
> tornano a 8000.

Se il template locale non è ancora taggato/pushato con le modifiche da propagare, punta
temporaneamente `_src_path` in `.copier-answers.yml` al path locale (Windows con `/`, es.
`C:/redberry/src/redberry-webapp-template` — **non** `/c/...`, **non** `file://`) e usa
`--vcs-ref=HEAD`. Ripristina `_src_path` al remote GitHub a fine lavoro.

Risoluzione conflitti:

- Leggi entrambi i lati, mai accettarne uno alla cieca. Per file riscritti in blocco
  (tipico salto di più minor, es. migrazione a bootstrap) parti dal lato template (render
  fresco, vedi passo 2) e riporta gli hunk del progetto da `git show HEAD:<file>`.
- Dopo l'update: `venv/Scripts/python -m pip install -r requirements.dev.txt` (il pin
  webkit è cambiato; gli script checks non reinstallano se ruff c'è già).
- `git add -A` per chiudere lo stato `UU`.

### 2. `align_to_template.py` — visibilità sul resto

```
cd C:/redberry/src/redberry-webapp-template
PATH="$PWD/venv/Scripts:$PATH" venv/Scripts/python.exe scripts/align_to_template.py <path-progetto> \
  --app-name "<Nome App>" --app-slug <slug> --report <scratchpad>/align_report.md
```

Il report ha 5 sezioni (owned-divergenti, comuni-divergenti-attesi, solo-nel-target,
solo-nello-skeleton, conteggio identici). **Nessuna sezione autorizza una scrittura
automatica.** Per ogni file segnalato:

- "Owned divergente" dopo `copier update` (tipicamente `app/core.py`, `app/main.py`,
  `Dockerfile`) = quasi sempre personalizzazione legittima (chiavi config, route, pacchetti
  apt) — verificalo leggendo il diff, non assumerlo.
- Pattern del template rimasto vecchio → porting mirato dell'hunk, mai del file intero.
- "Solo nel target" → business logic (va in `app/libs/` se framework-free) vs file meta.
- "Solo nello skeleton" → `app/libs/example.py` e il suo test sono placeholder: assenti è
  corretto. Il resto: valuta se serve.

Se un file non è chiaramente classificabile, chiedi all'utente.

### 3. Checklist finale — meccanica, non a memoria

ruff/mypy/pytest verificano che il codice giri, non che sia coerente con le guideline.

**3a. Grep meccanico (riporta ogni hit prima di giudicarlo). Mai grep su `.env`: escludilo.**

```bash
# web-py.md §7 / fastapi-auth.md — nessun wiring copiato nel progetto (deve stare in webkit bootstrap)
grep -rnE "AuthManager\(|_auth_gate|_security_headers|SlowAPIMiddleware|load_dotenv|uvicorn\.run|purge_loop|StaticFiles\(" app/

# uvicorn.md §2 — launcher separato, niente __main__ in main.py
ls app/__main__.py && grep -n '__name__ == "__main__"' app/main.py

# uvicorn.md §1 — env di progetto letto solo DOPO `from app.core import web`
grep -rn "os.getenv\|os.environ" app/

# niente NiceGUI residuo (codice, compose, .gitignore, .dockerignore)
grep -rn -i "nicegui" --exclude=.env --exclude-dir=venv --exclude-dir=.git --exclude-dir=.mypy_cache .

# docker.md — env_file: vietato (bind-mount + ENV_FILE); niente named volume; TZ su entrambi i compose
grep -n "env_file:" docker-compose*.yml
grep -nE "^\s+- [a-zA-Z_-]+:/[a-z]" docker-compose*.yml
grep -L "TZ=" docker-compose.yml docker-compose-dev.yml

# uvicorn.md §2 — workers mai esplicito (hit su ThreadPoolExecutor(max_workers=...) è legittimo)
grep -rn "workers=" app/ Dockerfile docker-compose*.yml

# python.md — niente print() in app/, niente datetime.now()/fromtimestamp() senza tz
grep -rn "print(" app/ --include=*.py
grep -rnE "datetime\.now\(\)|fromtimestamp\([^,)]*\)" app/ --include=*.py

# web-py.md §7 — niente hex nel codice Python (nel CSS di progetto solo dove non esiste un token)
grep -rnE "#[0-9A-Fa-f]{3,6}" app/ --include=*.py
```

Ogni hit va giudicato, non scartato automaticamente. **Drift nominale non è
un'eccezione accettabile**: lo scopo del template è uniformare. Un pezzo di wiring che
webkit fornisce già (login, gate, config page, security headers, ...) va rimosso dal
progetto, non tenuto "perché funziona uguale". Se il progetto ha qualcosa di generico che
webkit **non** fornisce, proponi all'utente di spostarlo in webkit (nuova minor) invece di
lasciarlo nel progetto.

**3b. Lettura esplicita (contro il codice reale, non a memoria):**
- `fastapi-auth.md` → "New project checklist"
- `web-py.md` §7
- `uvicorn.md` §1/§2 → env letto dopo `app.core`, launcher `app/__main__.py`, HOST/PORT via env
- `docker.md` §2/§5/§6/§7 → bind mount, due compose file, TZ, indirizzo bind
- `scripts.md` → line endings e exec bit (sotto)

**3c. Line endings e modi file** (`copier update` mergia contenuti, non modi):

```bash
git ls-files --eol scripts/            # .bat → w/crlf, .sh → w/lf
git update-index --chmod=+x scripts/*.sh && git ls-files -s scripts/*.sh   # atteso 100755
```

**3d. Docker image name**: il workflow pubblica `ghcr.io/<owner>/<nome repo GitHub>`
(`github.repository`), il compose usa lo slug con trattini (`app_slug` → `-`). Se il repo
GitHub ha un nome diverso (es. underscore, suffisso `_py`), `docker compose pull` non trova
l'immagine: segnalalo all'utente (convenzione: rinominare il repo con trattini).

**3e. Documentazione**: `AGENTS.md`, `CLAUDE.md`, `README.md` sono `_skip_if_exists`,
`copier update` non li tocca mai. Aggiornali a mano: mappa file (`core.py`, `__main__.py`,
`libs/`), comandi (`python -m app`, `set_password.bat|.sh`), nome immagine/container,
sezione "Allineamento al template"; `CLAUDE.md` nella forma puntatore
(`# CLAUDE.md` + `See [AGENTS.md](AGENTS.md) for project guidance.`).

### 4. Verifica

- `scripts/checks.bat` (Windows; `checks.sh` cerca `.venv`, su Windows non va) oppure gli
  stessi step a mano con la venv: `ruff check .`, `ruff format --check .`, `mypy app`, `pytest`.
- Test: le fixture vengono dal template (`web.config`/`web.metrics`/`web.auth` sostituiti su
  `tmp_path`); i test generici (login, semaforo, docs, root redirect) stanno in webkit e
  si tolgono dal progetto; **ogni test specifico del progetto va riportato**, non perso.
- Avvio reale (`python -m app --port <libera>`) e smoke test: `/health`, `/` → `/ui/`,
  `/ui/` → `/login`, asset, un endpoint API del progetto. Login e pagine UI in browser
  (tema chiaro/scuro) se il CSS è cambiato. Lo smoke test scrive nel `data/` reale: dillo.
- `python tools/check_versions.py` nel repo template: il progetto deve risultare `ok`.

### 5. Adozione Copier (se `.copier-answers.yml` manca)

Genera una skeleton temporanea con `copier copy` usando le risposte del progetto (passo 2
già lo fa), poi copia `.copier-answers.yml` dalla skeleton nel progetto target. Da quel
momento `copier update` è disponibile.

## Cosa NON fare

- **Non sostituire mai un file per intero** solo perché è "owned dal template" nel report.
- Non saltare `copier update` per andare dritti al confronto con la skeleton fresca.
- Non spuntare la checklist del passo 3 senza aver letto il file corrispondente.
- Non inventare `app_name`/`app_slug`.
- Non lasciare `_src_path` puntato al template locale.
- Non leggere né greppare `.env` (`python.md` §4).
- Non committare né pushare senza l'ok dell'utente.
