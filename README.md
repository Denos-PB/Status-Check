# Status Check

Status Check is a lightweight team commitment calendar built as a test assignment.
It includes authentication, monthly planning, commitment CRUD, status tracking, filtering, and optional AI-assisted form fill.

## What the app does

- Login/logout with cookie-based auth (no registration page)
- Monthly calendar view with commitments grouped by `deadline`
- Create, edit, delete commitments
- Quick status updates: `to_check`, `expired`, `done`, `not_actual`, `ideas_backlog`
- Filters by project and reviewer
- Automatic `expired` status refresh for overdue items
- Optional AI prefill for the new commitment form

## Tech stack

- **Backend:** FastAPI, SQLAlchemy 2.0 async, SQLite
- **Frontend:** Jinja2 templates, HTMX, TailwindCSS (CDN)
- **Other:** DeepSeek/Claude AI integration (optional), Docker Compose (optional)

## Project structure

```text
backend/
  app/
    api/routes/web.py          # HTML routes
    api/dependencies/auth.py   # auth dependencies
    core/                      # config, db init, security
    models/                    # User, Project, Commitment
    schemas/                   # form/request/response schemas
    services/                  # auth, commitments, AI parsing
frontend/
  templates/                   # Jinja pages/components
  static/                      # JS/CSS
```

## Local run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FRONTEND_DIR=../frontend
uvicorn app.main:app --reload
```

Open: [http://localhost:8000](http://localhost:8000)

On first start the app creates `backend/data/commitments.db` and seeds demo data.
If schema changed between versions, remove `backend/data/commitments.db` and restart.

### Demo login

- Email: `user@example.com`
- Password: `user123`

Unauthenticated access to `/` is redirected to `/login`.

## Docker run (optional)

```bash
docker compose up --build
```

The app will be available at [http://localhost:8000](http://localhost:8000).

## Configuration

Environment variables are optional.

Common settings:
- `FRONTEND_DIR` (default: `../frontend`)
- `DATABASE_URL` (default: local SQLite file)
- `SECRET_KEY`
- `DEEPSEEK_API_KEY` (required only for AI prefill)
- `DEEPSEEK_MODEL` (default: `deepseek-chat`)
- `DEEPSEEK_BASE_URL` (default: `https://api.deepseek.com/v1`)

Optional fallback:
- `CLAUDE_API_KEY`
- `CLAUDE_MODEL` (default: `claude-3-5-sonnet-latest`)

## AI prefill

On **New commitment**, describe task details in plain language and click **Fill with AI**.
The app parses title, people, project, status, and deadline suggestion.

Example prompt:

> Review API with Demo Reviewer by Friday, project Platform

## Notes / limitations

- Time/date picker UI format (AM/PM vs 24h) depends on browser/OS locale.

## License

See [LICENSE](LICENSE).
