# Backend

Django REST backend for AI Competency Assessor. Run commands below from the `Backend/` directory unless stated otherwise.

## Requirements

- Python 3.12 or newer for the pinned Django 6.1 release.
- Git for public repository processing.
- For Gemini-backed indexing and question generation, a Google AI Studio API key; compatible HTTP providers remain configurable.

## Create an environment and install dependencies

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

macOS/Linux activation: `source venv/bin/activate`.

## Environment configuration

Copy `.env.example` to `.env`, then edit the local copy. Django loads `Backend/.env` through `python-dotenv`; `.env` is local and must not be committed.

- Django: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL`.
- Repository processing: `REPOSITORY_PROVIDER`, `REPOSITORY_CLONE_TIMEOUT_SECONDS`, `MAX_REPOSITORY_SIZE_BYTES`, `MAX_REPOSITORY_FILE_COUNT`, `MAX_SOURCE_FILE_SIZE_BYTES`, `REPOSITORY_WORK_ROOT`.
- PDF upload limit: `MAX_SUBMISSION_PDF_SIZE` (bytes; default 10 MiB).
- Vector storage: `CHROMA_PERSIST_DIRECTORY`.
- Gemini: `GEMINI_API_KEY` and `GEMINI_TIMEOUT_SECONDS` (seconds; defaults to 120).
- Embeddings: `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, and `EMBEDDING_DIMENSIONS`; for Gemini the defaults are `google`, `gemini-embedding-001`, and 3072. The embedding model supports output dimensions from 128 through 3072; keep document and query configuration identical.
- LLM: `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_TIMEOUT_SECONDS`; Gemini defaults are `google` and `gemini-3.8-flash` when a key is configured.
- HTTP alternatives: `EMBEDDING_API_URL`, `EMBEDDING_API_KEY`, `LLM_API_URL`, and `LLM_API_KEY`.

Google calls use the official `google-genai` SDK. Question generation and evaluation request structured JSON and are validated by the existing application services. The HTTP embedding endpoint accepts an embeddings-style JSON request containing `model` and `input`, and returns an OpenAI-compatible `data` array of embeddings. The HTTP LLM endpoint accepts chat-completions-style `messages` and returns `choices[0].message.content`. HTTP URLs and model names depend on the service you configure. API keys are optional for endpoints that do not require bearer authentication. Do not put real keys in `.env.example` or documentation.

Database and media configuration are currently fixed in `config/settings.py`: SQLite is `Backend/db.sqlite3`, and uploaded media is stored under `Backend/media/`. JWT lifetimes are also configured in Django settings, not environment variables. ChromaDB and repository workspace paths can be overridden using the variables above; relative paths resolve under `Backend/`.

## Database migrations

Apply migrations to the configured database:

```powershell
python manage.py migrate
```

The database file is `db.sqlite3` in this directory. Back it up before schema changes; do not delete or recreate it to resolve migration issues.

## Run the development server

```powershell
python manage.py runserver
```

The default local address is `http://127.0.0.1:8000/`; API routes are under `/api/`, and admin is under `/admin/`.

## Tests and Django checks

```powershell
python manage.py test
python manage.py check
```

## Local data directories

- SQLite database: `Backend/db.sqlite3`.
- ChromaDB persistent store: `Backend/chroma_data/` by default (`CHROMA_PERSIST_DIRECTORY` overrides it).
- Gemini uses a model-and-dimension-specific collection name by default, separate from the legacy `submission_content` collection. Existing vectors are not converted automatically; select a fresh collection and reprocess/re-index submissions when migrating embedding profiles. Do not point incompatible profiles at the same collection.
- Uploaded PDFs: `Backend/media/`.
- Temporary repository worktrees: `Backend/repository_work/` by default (`REPOSITORY_WORK_ROOT` overrides it).

These locations can contain sensitive assessment or user data; keep them out of version control and include them in an appropriate backup/retention plan. Background processing currently uses in-process workers and is not durable across application restarts.
# Local demo data

For a local development database, create the demo workflow with:

```powershell
cd Backend
.\venv\Scripts\python.exe manage.py seed_demo_data
```

The command refuses to run when `DEBUG` is false. It is intentionally explicit instead of running from Django startup: startup hooks can execute during tests, migrations, or in every web worker. The command uses the `demo_` username namespace, creates only missing rows, and preserves the fields and relationships of already existing batches, tasks, and submissions. Run it against a local development database only; it does not reset the database.

Newly created demo accounts use the temporary local-only password `LocalDemo-2026!`. Their usernames and emails are:

| Role | Username | Email |
| --- | --- | --- |
| Faculty | `demo_faculty` | `demo_faculty@example.test` |
| TA | `demo_ta1`, `demo_ta2`, `demo_ta3` | `demo_ta1@example.test`, etc. |
| Trainee | `demo_trainee1_1` through `demo_trainee3_3` | Matching `@example.test` addresses |

An existing account with one of these usernames is left unchanged, including its password and active status. If a reserved demo username already exists with a different role, the command stops. Therefore the listed password is guaranteed only for accounts created by the command, and these credentials must never be deployed.

The demo workflow includes three batches, assigned TAs and trainees, active rubric criteria with L1–L4 descriptions, tasks, two sample submissions, generated questions, saved answers, evaluation and review records, and one draft plus one published report. The sample repository is a public test URL; processing still requires a working repository provider and AI/embedding configuration.

The read-only audit endpoint is available at `/api/audit-events/`. Faculty see events for their batches and their own unassigned events; TAs see events for assigned batches; trainees cannot access the endpoint.
