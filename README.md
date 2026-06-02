# Status Check

Test project: shared commitment calendar with login, CRUD, statuses, and filters.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0 (async), SQLite, Jinja2
- **Frontend:** Jinja2 templates, TailwindCSS (CDN)
- **Infra:** Docker (optional)

## Structure

```
backend/app/
  api/routes/       # HTML routes (web.py)
  api/dependencies/ # auth (cookie session)
  core/             # config, database (+ seed)
  models/           # User, Project, Commitment (+ statuses)
  schemas/          # auth + commitment forms
  services/         # auth_service, commitment_service
frontend/templates/
```

## Quick start

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
export FRONTEND_DIR=../frontend
uvicorn app.main:app --reload
```

Open http://localhost:8000 — DB file `backend/data/commitments.db` is created automatically.

If you had an older database schema, delete `backend/data/commitments.db` and restart.

**Demo login:** `user@example.com` / `user123`  
Unauthenticated visits to `/` redirect to `/login`.

## Docker

```bash
docker compose up --build
```

## Features (requirements)

- Login / logout (shared SQLite database)
- Month calendar with commitments on **deadline**
- Create, edit, change status, delete commitments
- Statuses: `to_check`, `expired`, `done`, `not_actual`, `ideas_backlog`
- Filters: **project**, **reviewer**
- `expired` is applied when loading the calendar (deadline passed, not done/not actual)
- **AI fill**: on "New commitment", describe a task in plain language -> form is pre-filled (requires `OPENAI_API_KEY`)

## Optional `.env`

Not required. Override `SECRET_KEY`, `DATABASE_URL`, or set `OPENAI_API_KEY` for AI fill.

**AI demo prompt** (after login -> New commitment):

> Review API with Demo Reviewer by Friday, project Platform

## License

See [LICENSE](LICENSE).
