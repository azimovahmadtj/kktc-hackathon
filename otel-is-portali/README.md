# Otel İş Portalı

Hotel & hospitality job platform for Northern Cyprus.
**Django 5.2** (SQLite by default, PostgreSQL optional), AI CV matching with the **Claude API**, interface in **Türkçe / English / Русский**.

## Quick start (Windows), nothing to install except Python

The database is **SQLite**, which is built into Python: the file `db.sqlite3` is created automatically.

```bat
cd otel-is-portali
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

macOS / Linux: the same, but `python3 -m venv .venv`, `source .venv/bin/activate` and `cp .env.example .env`.

For AI CV matching, put your Claude key in `.env` (https://platform.claude.com/settings/keys):

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without it CV matching uses the free built-in engine.

### Optional: PostgreSQL

For production, or if you prefer PostgreSQL:

1. Start PostgreSQL: `docker compose up -d`, or install PostgreSQL 16 and run in *SQL Shell (psql)*:
   ```sql
   CREATE USER otelportal WITH PASSWORD 'otelportal' CREATEDB;
   CREATE DATABASE otelportal OWNER otelportal;
   ```
2. In `.env` set `DATABASE_URL=postgres://otelportal:otelportal@127.0.0.1:5432/otelportal`
3. Run `python manage.py migrate` and `python manage.py seed_demo` again (the new database starts empty).

Open http://127.0.0.1:8000

| Demo account | Email | Password |
|---|---|---|
| Employer (Kaya Palazzo Resort) | `isveren@demo.com` | `Demo12345!` |
| Job seeker | `aday@demo.com` | `Demo12345!` |

Admin panel: `python manage.py createsuperuser`, then http://127.0.0.1:8000/admin/

## Open the site on your phone

Phone and computer must be on the **same Wi-Fi**.

```bat
python manage.py lan
```

It prints the address for your phone, e.g. `http://192.168.1.5:8000`. Open it in the phone's browser.
If the page does not open, allow Python through the Windows firewall (Windows asks on the first run, so choose
"Private networks" and click "Allow").

From anywhere (mobile data, another city): install `cloudflared`, run `python manage.py runserver` and in a second window
`cloudflared tunnel --url http://localhost:8000`. It prints an `https://….trycloudflare.com` link that works on any phone
while both windows are open.

## View the database

- **Admin panel (easiest):** `python manage.py createsuperuser` (enter an email and password), then open
  http://127.0.0.1:8000/admin/. You can browse and edit users, profiles, job ads, applications and CV analyses.
- **DB Browser for SQLite:** install it from https://sqlitebrowser.org, then open the `db.sqlite3` file in the project
  folder. The *Browse Data* tab shows every table (`portal_user`, `portal_job`, `portal_application`, …).
  Close it before running `migrate`.

## Features

- **Landing page** (`/`) with job ads from the database
- **Sign up** (`/register/`) as a *job seeker* or *employer (hotel)*; you are logged in straight away
- **Employer panel** (`/panel/`): open ads, applications, waiting for review, status tiles, best-matching candidates, latest applications
- **Applications** (`/applications/`): the employer changes status (sent → reviewed → interview → accepted / rejected) and downloads CVs; the candidate sees changes with a notification dot
- **My listings** (`/my-jobs/`): create, edit, pause and delete job ads
- **Job market** (`/jobs/`): search and filters; job seekers see their match score and apply
- **Profile** (`/profile/`): phone, experience, department, availability, accommodation, languages, bio, CV upload (PDF/DOC/DOCX, max 5 MB)
- **AI matching** (`/ai/match/`): see below

CVs are not public: only the candidate and the employers they applied to can download them.

## CV matching: free by default, Claude optional

The job seeker opens **AI matching** (`/ai/match/`) and clicks **"Analyse my CV"**. Two engines:

| | Free smart matching (default) | Claude (if `ANTHROPIC_API_KEY` is set) |
|---|---|---|
| Code | `portal/local_matcher.py` | `portal/ai.py` |
| Cost | free, no API, works offline | ~2–10 cents per analysis |
| Speed | under 1 second | 10–60 seconds |
| How | keyword dictionaries (TR / EN / RU) + the platform score formula | LLM reads and understands the CV |

**Free engine:** extracts text from the PDF (`pypdf`) or DOCX, then finds:

- department (receptionist / resepsiyon / администратор → front office, …)
- spoken languages
- years of experience (explicit "3 years / 3 yıl / 3 года" or date ranges like "2019 – present"; education and age lines are ignored)
- availability (seasonal / full-time / part-time)
- skills (Opera PMS, HACCP, first aid, …)

It then scores every open job with the platform formula (a different department lowers the score) and explains each match in the
interface language. Add words to the dictionaries at the top of `local_matcher.py` to improve recognition.
Scanned-image PDFs have no text, so ask for a text PDF or DOCX.

### Claude engine (optional)

When `ANTHROPIC_API_KEY` is set, `portal/ai.py` sends Claude:

1. the CV (PDF as a document, DOCX as extracted text; old `.doc` files are not supported, so upload PDF/DOCX),
2. the catalog of active job ads (up to `AI_MAX_JOBS_IN_PROMPT`, default 150).

Claude returns **structured JSON** (guaranteed by a JSON schema):

- facts from the CV: summary, experience, department, languages, availability, skills, a suggested profile bio
- up to 5 matching job ads with a 0–100 fit score, reasons and gaps, written in the user's interface language

The result is validated (Pydantic), job ids are checked against the database, and the analysis is stored in `CvAnalysis`
(with token usage, visible in the admin). The candidate can copy the detected facts into their profile with one click.

| Setting (`.env`) | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | required for AI matching |
| `ANTHROPIC_MODEL` | `claude-opus-5-5` | Claude model |
| `AI_MAX_JOBS_IN_PROMPT` | `150` | newest active job ads sent to the model |
| `AI_TIMEOUT_SECONDS` | `120` | request timeout |

Details:

- **Prompt caching:** the system prompt and job catalog are a cached prefix, so repeated analyses are cheaper and faster.
- **Refusal fallback:** `fallbacks: "default"` is enabled, which re-runs a request on Anthropic's recommended fallback model if a safety classifier declines it.
- **Limits:** one analysis per 30 seconds and 20 per day per user (`AI_COOLDOWN`, `AI_DAILY_LIMIT` in `portal/views.py`).
- **Cost:** each analysis is one Claude request. With Claude Opus 5.5 ($4 / $20 per million input / output tokens), a typical CV plus 50 job ads is roughly 10–20K input tokens, so about 5–10 cents. Switch `ANTHROPIC_MODEL` to `claude-sonnet-5-5` for lower cost.
- **Request handling:** the analysis runs inside the web request and can take up to a minute. For heavy traffic, move it to a background worker (Celery / RQ).

### Rule-based match score (0–100)

Shown on job ads and to employers (`portal/scoring.py`):

| Criterion | Points |
|---|---|
| Department matches | 30 |
| Required languages spoken | 25 |
| Experience vs. required years | 20 |
| Availability fits the employment type | 15 |
| Accommodation (not needed, or provided) | 10 |

## Languages

Only Turkish (default), English and Russian are enabled (`LANGUAGES` in `otelportal/settings.py`).
Translations: `locale/tr/LC_MESSAGES/django.po`, `locale/ru/LC_MESSAGES/django.po`. After editing, compile (no GNU gettext needed):

```bat
python tools/compile_messages.py
```

Landing page texts are in `static/js/landing.js` (the `I18N` object).

## Tests

```bat
python manage.py test portal
```

Tests run on whichever database is configured (with PostgreSQL the DB user needs `CREATEDB`).
The AI tests use a mocked Claude client and do not call the API.

## Project structure

```
otelportal/        settings (SQLite by default, PostgreSQL via DATABASE_URL, .env loader), urls
portal/            models, views, forms, scoring, local_matcher (free CV matching), ai (Claude), admin, tests, seed_demo
templates/         landing.html, auth/ (login, register), app/ (panel pages, ai_match.html)
static/css, js     landing + app styles and scripts
locale/            tr, ru translations
tools/             compile_messages.py
docker-compose.yml optional local PostgreSQL
```

## Production notes

Use PostgreSQL in production. Set `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=yourdomain.com`, `DATABASE_URL` and `ANTHROPIC_API_KEY`
as environment variables. Run `python manage.py collectstatic` and serve with gunicorn/uwsgi behind nginx.
Never commit `.env`.
