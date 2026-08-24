# WM CRM MVP

A small, mobile-first internal lookup system for architecture/design field teams. It keeps clients, people, properties, units, projects, and per-project roles relational while offering one broad search box.

## Architecture

```text
Browser (server-rendered Jinja + responsive CSS)
              │
        FastAPI monolith
     ┌────────┼─────────┐
 Auth/RBAC  Search   CSV review
              │
      SQLAlchemy + Alembic
              │
          PostgreSQL
```

```text
app/
  main.py       web pages, CRUD API, CSV/review endpoints
  models.py     normalized SQLAlchemy domain model
  search.py     cross-entity project lookup
  auth.py       signed sessions and role checks
  templates/    responsive field and office screens
  static/       dependency-free CSS
alembic/        database migrations
tests/          relationships, search, RBAC, import approval
```

## Start with Docker (recommended)

1. Copy `.env.example` to `.env`.
2. Replace every `change-me` value and set a long random `SECRET_KEY`.
3. Run `docker compose up --build`.
4. Open <http://localhost:8000>. Startup migrates and seeds the database. Sign in using an account configured in `.env`.

Search accepts partial addresses, units, legal names, nicknames, companies, project names, phone numbers, and emails.

## Run without Docker

Python 3.12 and PostgreSQL are recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit DATABASE_URL and secrets in .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

For quick local evaluation, `DATABASE_URL=sqlite:///./wmcrm.db` is supported. Production should use PostgreSQL.

## Workflows

- `FIELD_USER`: global search and detail screens; phone and email links open the device dialer/mail app.
- `OFFICE_USER` or `ADMIN`: field access plus `/admin`, contact corrections, CSV upload, and review actions.
- Daily project work lives at `/projects`. Office users can create a property/project, choose an initial client, then assign multiple people and companies with project-specific roles such as Site Contact, Superintendent, GC, Architect, or Engineer.
- Contacts and companies have dedicated searchable directory pages. Admin is reserved for imports, duplicate review, and data verification.
- Uploading `WM Client list.xlsx` reads the `current client list` tab directly and stages complete client rows. Name, nickname, company, address, office/fax/cell phones, notes, and email are mapped; placeholder `-` values are treated as blank.
- CSV rows require `entity_type` (`contact` or `company`). All uploads become `PENDING`. Approve creates verified production rows; reject and needs-correction do not.
- Imports preserve source filename/type, timestamps, reviewer, and status. Rows without a legal name are skipped and reported instead of creating ambiguous contacts.
- Import review deterministically flags exact normalized phone/email matches, similar names within the same company, and similar company names. Reviewers explicitly choose Create New, Update Existing, Merge Missing Fields, or Skip; uncertain records are never merged automatically.

API documentation is at <http://localhost:8000/docs>.

## Tests

Run `pytest -q`. Tests use isolated in-memory SQLite and cover entity relationships, partial address/unit/name/company/phone/email/project search, permissions, and staged approval.

## MANUAL CONFIGURATION

Before a shared or production deployment:

1. **PostgreSQL:** create a database and dedicated least-privilege user. Put its SQLAlchemy URL in `.env` as `DATABASE_URL`. Docker defaults are local-only.
2. **Session secret:** generate a long random value (for example, `python -c "import secrets; print(secrets.token_urlsafe(48))"`) and put it in `.env` as `SECRET_KEY`.
3. **Initial accounts:** set unique emails and strong passwords for `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `FIELD_EMAIL`, and `FIELD_PASSWORD` in `.env`. Seed is idempotent; changing an existing password currently requires a database update.
4. **Production TLS/domain:** terminate HTTPS at your cloud load balancer/reverse proxy and configure domain/DNS there.
5. Do not commit `.env`. No Gmail connection, OAuth credential, or API key is required.

## MVP boundary

The app intentionally uses broad SQL matching and normalized phone digits rather than Elasticsearch. Roles are strings, so new roles require no migration. Staging is source-neutral, allowing future document/email/AI proposals without direct writes to trusted tables. Full event audit history, password administration, bulk project/property editors, trigram ranking, and public-record integrations are later increments.
