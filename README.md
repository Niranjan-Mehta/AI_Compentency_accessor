# AI Competency Assessor

AI Competency Assessor is a web application for managing practical technical assessments. Faculty define competency rubrics and tasks, trainees submit a repository and (when required) a project PDF, and authorized teaching staff review assessment evidence and publish reports.

## The problem it addresses

Practical programming assessments often involve scattered task instructions, inconsistent scoring, and time-consuming reviews. This project brings task assignment, structured rubric scoring, submission evidence, review, and reporting into one role-based workflow.

## Features

- Role-aware accounts for faculty, teaching assistants (TAs), and trainees.
- Batch management and batch-scoped task assignment.
- Rubrics with criteria and competency levels.
- Task creation and assignment to batches.
- Git repository URL and PDF submission, with processing status.
- Repository and PDF text processing, configurable embeddings, and submission-scoped ChromaDB retrieval.
- Assessment questions, answer submission, review, score overrides, and reports, subject to configured AI providers.
- Django REST APIs consumed by a React frontend.

AI-related operations use configurable backend providers. Google Gemini is supported through Google's official Python SDK; credentials remain on the backend and are read from its local environment. No AI model is bundled with the project, and a live request still depends on provider availability and quota.

## Technology stack

- Frontend: React, Vite, JavaScript/JSX, and TypeScript tooling.
- Backend: Python, Django, Django REST Framework, and Simple JWT.
- Relational data: SQLite.
- Repository evidence: configurable repository provider (public Git is available for testing; Gitea provider support is separate).
- Vector storage: persistent local ChromaDB.
- PDF extraction: PyMuPDF.

## Architecture

The browser-based React app calls the Django REST API. Django handles authentication, authorization, batches, rubrics, tasks, submissions, assessment workflows, and reports. Repository processing and PDF extraction feed text chunks and metadata to the configured embedding provider and persistent ChromaDB store. Gemini LLM calls use the official Google Gen AI SDK and structured JSON output; HTTP-compatible providers remain available. Repository content is treated as data and is not executed by the processing workflow.

The MVP schedules heavier jobs in a small in-process worker pool. It is suitable for local development, but queued work is not durable across a server restart.

## User roles

- **Faculty:** manage their users/batches, rubrics, tasks, and assessment/report workflows for their assigned work.
- **Teaching Assistant (TA):** view and review work for batches assigned to them, subject to API permissions.
- **Trainee:** view their assigned work, submit project evidence, answer generated questions, and view reports made available to them.

The backend enforces role and object-level access; frontend visibility alone is not an authorization boundary.

## Assessment workflow

1. Faculty create a batch, enroll trainees, and assign TAs.
2. Faculty define and activate a rubric, then create a task and assign it to one or more batches.
3. A trainee submits the repository URL, branch, and required PDF.
4. Authorized processing clones the selected repository revision, extracts supported source and PDF text, and indexes chunks for that submission. The submission processing endpoint is separate from the later question-generation endpoint.
5. The configured LLM provider may generate assessment questions; the trainee submits answers.
6. Faculty or assigned TAs review the assessment evidence, record permitted criterion overrides, and complete review.
7. Faculty prepare and publish reports; trainees can access reports according to API permissions.

Provider configuration and external service availability determine whether AI-dependent steps can run.

## Project structure

```text
AI_Compentency_Accessor/
├── README.md
├── .gitignore
├── Backend/
│   ├── apps/                 # Django domain apps and migrations
│   ├── config/               # Django settings, URL config, ASGI/WSGI
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
└── Frontend/
    ├── src/                  # React app, views, context, API client
    ├── public/               # Static assets
    ├── package.json
    ├── package-lock.json
    ├── .env.example
    └── README.md
```

Runtime data such as the SQLite file, uploaded media, repository workspaces, and ChromaDB persistence is kept under `Backend/` by default and should not be committed.

## Prerequisites

- Python 3.12 or newer for the pinned Django 6.1 release.
- Node.js and npm (use a current LTS release compatible with Vite 8).
- Git, for processing public Git repositories.
- A Gemini API key for the configured Google LLM and embedding providers, or compatible HTTP providers instead.

## Backend setup

From the repository root, see [Backend/README.md](Backend/README.md) for the complete backend setup. In brief:

```powershell
cd Backend
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit the local `.env` with suitable development values. Do not commit it. See the backend guide for provider requirements and the configured database/storage paths.

## Frontend setup

```powershell
cd Frontend
npm ci
Copy-Item .env.example .env
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000/api`; configure `VITE_API_BASE_URL` in the local frontend `.env` if the backend API is hosted elsewhere. See [Frontend/README.md](Frontend/README.md).

## Database migrations

The current backend uses `Backend/db.sqlite3`. To create/update its schema in a development environment:

```powershell
cd Backend
python manage.py migrate
```

Back up any database containing data before schema changes. Never remove or replace a database to resolve a migration issue without a separate, reviewed recovery plan. Migration files under each app's `migrations/` directory are part of the application and must be preserved.

## Run locally

Start the backend in one terminal:

```powershell
cd Backend
venv\Scripts\Activate.ps1
python manage.py runserver
```

Start the frontend in another:

```powershell
cd Frontend
npm run dev
```

Open the Vite URL printed in the terminal (the package script uses port 3000). Django's default development API is `http://127.0.0.1:8000/api/`.

## API overview

The API is rooted at `/api/`; JWT authentication endpoints are under `/api/auth/`.

- Authentication and accounts: `/api/auth/login/`, `/api/auth/token/refresh/`, `/api/auth/profile/`, `/api/auth/users/`, `/api/auth/invite/`, `/api/auth/create-user/`, `/api/auth/logout/`.
- Batches: `/api/batches/` and batch membership actions.
- Rubrics: `/api/rubrics/`.
- Tasks: `/api/tasks/`.
- Submissions and processing: `/api/submissions/`, including processing, status, retrieval, and question-generation actions.
- Assessments: `/api/assessment-runs/`, `/api/questions/`, plus answer, evaluation, review, and scoring actions.
- Reports: `/api/reports/`, including preparation and publishing actions.
- Audit events: read-only `/api/audit-events/`, scoped to the caller's role and batch assignments.
- Django admin: `/admin/`.

Exact methods, filters, and access rules are defined by the backend routes and viewsets.

## Tests and checks

Backend Django tests:

```powershell
cd Backend
python manage.py test
```

Frontend TypeScript check and production build:

```powershell
cd Frontend
npm run lint
npm run build
```

## Environment configuration

Copy the `.env.example` template for each app to a local `.env` and set only values appropriate to your environment. Backend variables include Django host/debug/email settings, repository processing limits/provider, ChromaDB path and collection, `GEMINI_API_KEY`, provider selectors, model names and embedding dimensions. The default Gemini models are `gemini-3.8-flash` and `gemini-embedding-001`; the default embedding size is 3072 dimensions. Frontend uses `VITE_API_BASE_URL`. SQLite path, media path, and JWT lifetimes are currently defined in Django settings rather than exposed as environment variables. Never commit credentials or local `.env` files. Changing embedding model or dimensions requires a distinct Chroma collection and re-indexing submissions.

## Security notes

- Set a unique strong `SECRET_KEY`, `DEBUG=False`, and production `ALLOWED_HOSTS` before deployment. The development defaults are not production-safe.
- Use HTTPS and restrict CORS origins to trusted frontend origins in deployed environments.
- Protect provider credentials and use endpoints you trust; do not place backend secrets in frontend environment variables.
- Uploaded PDFs and repository contents are untrusted input. The system does not execute repository code.
- SQLite, uploaded media, repository workspaces, and ChromaDB contain application/user data; protect and back them up according to your retention policy.
- The default in-process background worker is not a durable production queue.

## Current limitations

- No production deployment configuration, durable job queue, or object storage is included.
- SQLite and local ChromaDB are configured for local/small-scale use.
- AI processing requires a configured external provider and available quota; provider errors can delay or fail AI-dependent jobs. No model is bundled with the project.
- Gitea credentials and authenticated repository access are not configured.
- Frontend and backend should be deployed behind suitable production web servers with secure environment configuration before real use.

## Local demonstration data

To create demonstration records on a local database, run the explicit development-only command described in [Backend/README.md](Backend/README.md#local-demo-data). It is not run automatically on server startup. The command refuses to run with `DEBUG=False`; its temporary demo credentials are for local testing only.
