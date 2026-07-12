---
name: align-to-template
description: Use when asked to align, update, or migrate an existing FastAPI+NiceGUI project to redberry-webapp-template — phrases like "allinea questo progetto al template", "porta X sul template", "aggiorna il progetto al template". Drives alignment via `copier update` (safe 3-way merge) plus a reviewed diff for drift the template never touched — never a blind file overwrite.
---

# Align to Template

Guida un allineamento completo di un progetto esistente a `redberry-webapp-template`.

**Perché questa skill esiste, e perché questa versione**: la v1 usava
`scripts/align_to_template.py` per generare una skeleton fresca e poi **sostituiva
integralmente** i file "owned dal template" (main.py, Dockerfile, docker-compose*,
login.html, script). Testata su un progetto reale (`news_scraper`), quella
sostituzione ha cancellato 316 righe di route applicative da `app/main.py` e
personalizzazioni Docker legittime e necessarie (`NICEGUI_STORAGE_PATH`, `shm_size`
per Playwright, volume `./debug`) — nessuno di questi file è mai puro boilerplate
in un progetto maturo. "Sostituzione integrale" è l'errore opposto a quello che la
skill doveva risolvere: non lascia più pezzi vecchi indietro, ma distrugge lavoro
legittimo. **Non farlo mai più.**

## I due meccanismi, in ordine — non intercambiabili

1. **`copier update`** — merge a 3 vie basato su `.copier-answers.yml`: confronta
   template-alla-generazione vs template-attuale vs stato-attuale-del-progetto.
   Applica solo ciò che il template ha davvero cambiato; lascia intatto tutto il
   resto, comprese le personalizzazioni dentro file "owned dal template". Dove non
   riesce a mergiare automaticamente, lascia conflict marker (`<<<<<<<`) — mai
   silenzio. **Questo è il meccanismo primario, sempre da provare per primo.**
2. **`scripts/align_to_template.py`** — genera una skeleton fresca e confronta con
   il progetto target. Serve solo per **visibilità**: trova drift che il template
   non ha mai toccato (il progetto si è allontanato dalle convenzioni per conto
   suo) o file completamente mancanti/aggiuntivi. **Non scrive mai nulla da solo.**
   Ogni riga del suo report è materia di revisione manuale, mai di sostituzione
   automatica.

## Input

`args`: `<path-progetto> [app_name] [app_slug]`

Se `app_name`/`app_slug` non sono forniti, cercali nel progetto target prima di
procedere (es. `grep -r "cookie_name=" app/ui/router.py`, `_APP_NAME` in
`app/ui/pages.py`) — non inventarli.

## Passi

### 0. Sicurezza — sempre prima di toccare qualunque file

`git status` sul progetto target. Se ci sono modifiche non committate, `git stash
push -u` prima di procedere (recuperabile, mai perso). Non chiedere conferma per lo
stash stesso — è reversibile — ma se lo stash contiene lavoro sostanziale, segnalalo
esplicitamente all'utente prima di continuare.

### 1. `copier update` — passo primario

Verifica che il progetto abbia `.copier-answers.yml` (se manca, vedi passo 5 prima
di procedere). Poi, dalla root del progetto target:

```
copier update --defaults
```

Se il template locale (questo repo) non è ancora taggato/pushato con le modifiche
che vuoi propagare, punta temporaneamente `_src_path` in `.copier-answers.yml` del
progetto target al path locale del template (path Windows con `/`, es.
`C:/redberry/src/python/redberry-webapp-template` — **non** notazione mingw
`/c/...`, **non** `file://`: entrambe falliscono con `ValueError: Local template
must be a directory` su questo setup) e usa `--vcs-ref=HEAD` per non confrontare
contro l'ultimo tag. Ripristina `_src_path` al valore originale (remote GitHub) a
fine test/allineamento — non lasciarlo puntato al path locale in modo permanente.

Risolvi eventuali conflict marker leggendo entrambi i lati — mai accettare un lato
alla cieca.

### 2. `align_to_template.py` — visibilità sul resto

```
venv/Scripts/python.exe scripts/align_to_template.py <path-progetto> \
  --app-name "<Nome App>" --app-slug <slug> --report /tmp/align_report.md
```

Il report ha 4 sezioni (owned-divergenti, comuni-divergenti-attesi, solo-nel-target,
solo-nello-skeleton). **Nessuna sezione autorizza una scrittura automatica.** Per
ogni file segnalato:

- Se `copier update` lo ha già lasciato intatto ed è nella sezione "owned
  divergente", la divergenza residua è quasi certamente personalizzazione
  legittima (route applicative, config Docker specifiche) — verificalo leggendo il
  diff riga per riga, non assumerlo.
- Se il diff mostra chiaramente un pattern del template rimasto vecchio (es.
  `pages.py` senza `_page_setup`/`_header`/`_footer`, `main.py` senza
  `resolve_env_path()`), quella è materia di porting mirato: modifica solo l'hunk
  interessato, mai il file intero.
- File "solo nel target" → business logic reale (porta se serve) vs file di
  lavoro/meta del progetto (lascia stare, verifica solo che non duplichi qualcosa
  che il template offre già).
- File "solo nello skeleton" → valuta se il progetto ne ha bisogno.

Se un file non è chiaramente classificabile, chiedi all'utente — non indovinare.

### 3. Checklist finale — meccanica, non a memoria

Questo passo non è opzionale e non si spunta "a occhio": ruff/mypy/pytest
verificano che il codice giri, non che sia coerente con le guideline (colori,
spaziature, pattern Docker/auth). Qui si verifica quello — con grep dove
possibile, con lettura esplicita dove serve giudizio.

**3a. Grep meccanico (esegui sempre, riporta ogni hit prima di ignorarlo):**

```bash
# nicegui.md — niente hex fuori da login.html; eccezioni legittime: chart
# rendering (matplotlib/plotting), template PDF (.html.jinja per documenti) —
# verifica comunque ogni hit, non escluderle a priori dal grep
grep -rnE "#[0-9A-Fa-f]{3,6}" app/ --include=*.py | grep -v login.html

# nicegui.md — classi Tailwind al posto di Quasar
grep -rnE '"(text-xl|text-lg|text-sm|font-bold|font-semibold|w-full|p-[0-9]|m-[0-9]|rounded-|bg-gray|bg-white)' app/

# nicegui.md — dark mode hardcoded invece di app.storage.user
grep -rn "ui.dark_mode(True)\|ui.dark_mode(False)\|ui.dark_mode(value=True)\|ui.dark_mode(value=False)" app/

# docker.md — env_file: è vietato (deve essere bind-mount + ENV_FILE)
grep -n "env_file:" docker-compose*.yml

# docker.md — named volumes invece di bind mount (pattern sospetto: nome senza ./ o /)
grep -nE "^\s+- [a-zA-Z_-]+:/[a-z]" docker-compose*.yml

# docker.md §7 — TZ deve essere in environment: su entrambi i compose
grep -L "TZ=" docker-compose.yml docker-compose-dev.yml

# nicegui.md — NICEGUI_STORAGE_PATH deve puntare dentro un bind mount, non default
grep -n "NICEGUI_STORAGE_PATH" docker-compose.yml docker-compose-dev.yml

# uvicorn.md §2 — workers non deve mai essere passato esplicitamente
grep -rn "workers=" app/main.py Dockerfile docker-compose*.yml

# uvicorn.md — docs_url/redoc_url/openapi_url devono essere gated su DEV
grep -n "docs_url\|redoc_url\|openapi_url" app/main.py

# python.md — niente print() fuori da script CLI (scripts/)
grep -rn "print(" app/ --include=*.py

# python.md — timezone: niente datetime.now()/fromtimestamp() bare (senza tz=)
grep -rnE "datetime\.now\(\)|fromtimestamp\([^,)]*\)" app/ --include=*.py
```

Ogni hit va giudicato, non scartato automaticamente: es. hex in un file di
plotting o in un template PDF sono legittimi, hex in `pages.py`/`components.py`
no. Segnala esplicitamente cosa hai trovato e perché lo consideri conforme o
no — non saltare la riga di output.

**Drift nominale (nomi/struttura diversi ma stesso comportamento) NON è
un'eccezione accettabile.** Lo scopo del template è uniformare tutte le app
che ne ereditano — un middleware di auth che fa la stessa cosa ma si chiama
`ui_auth_gate`/`_UI_SOCKET_PREFIX` invece di `_auth_gate`/`_UI_PREFIX`/
`_LOGIN_PATHS`/`_UI_BYPASS_PREFIXES` (pattern canonico in `app/main.py.jinja`)
è materia di fix, non di nota a margine. Non liquidarlo con "funzionalmente
equivalente, non lo tocco" — allinealo al pattern canonico nello stesso passo
in cui lo trovi.

```bash
# uvicorn.md / fastapi-auth.md — nome canonico del gate middleware e delle sue
# costanti; qualunque variante (nome diverso, costanti diverse) va allineata
grep -n "_auth_gate\|_UI_PREFIX\|_LOGIN_PATHS\|_UI_BYPASS_PREFIXES" app/main.py
```

Se il grep non trova questi 4 simboli esatti in `app/main.py`, il middleware
va riscritto per farli comparire — confrontando riga per riga con
`redberry-webapp-template/app/main.py.jinja` (il blocco tra `app = FastAPI(`
e `@app.get("/health")`), non solo "verificato che funzioni allo stesso modo".

**3b. Lettura esplicita (contro il codice reale del progetto target, non a memoria):**
- `fastapi-auth.md` → "New project checklist"
- `nicegui.md` §11 → checklist completa
- `uvicorn.md` §1/§2 → resolve_env_path/entrypoint singolo, HOST/PORT via env
- `docker.md` §2/§5/§6/§7 → bind mount, due compose file, TZ, indirizzo bind

Ogni voce va verificata leggendo il file corrispondente.

### 4. Verifica

- `scripts/checks.bat`/`.sh` nel progetto target (ruff/mypy/pytest)
- Avvio reale e smoke test in browser della golden path

### 5. Adozione Copier (se `.copier-answers.yml` manca)

Genera una skeleton temporanea con `copier copy` usando le risposte del progetto
(passo 2 già lo fa), poi copia `.copier-answers.yml` dalla skeleton nel progetto
target. Da quel momento `copier update` è disponibile per i prossimi allineamenti.

## Cosa NON fare

- **Non sostituire mai un file per intero** solo perché è nella lista "owned dal
  template" del report — quella lista è solo classificazione per il diff, non
  un'autorizzazione a sovrascrivere.
- Non saltare `copier update` per andare dritti al confronto skeleton-fresca — è il
  meccanismo più sicuro, va sempre provato per primo.
- Non spuntare la checklist del passo 3 senza aver letto il file corrispondente.
- Non inventare `app_name`/`app_slug` se non espliciti: cercarli nel progetto.
- Non lasciare `_src_path` puntato al template locale dopo un test/allineamento.
