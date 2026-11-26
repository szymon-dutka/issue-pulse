# issue-pulse

issue-pulse checks how responsive the maintainers of an open-source project are. It imports
issue and comment metadata from the GitHub REST API into PostgreSQL and computes, for each
repository, how quickly and how often maintainers reply to issues opened by outside
contributors.

The data pipeline and the metrics are done and tested. A JSON API and a simple web UI are next.

## What it measures

For each repository I look at issues opened in the last 90 days by people outside the team,
so issues from owners, members and collaborators are left out. A maintainer response is the
first comment from one of those people, as long as it's not a bot.

From that sample I compute two things:

- the median time to the first maintainer response, in hours,
- the share of issues that got a response within 30 days. Only issues older than 30 days are
  counted here, so new issues don't lower the result.

If fewer than 10 issues are available, the metric is returned as empty instead of a number
based on two or three issues. The sample sizes are always returned, so it's clear what each
number is based on.

Only issues updated within the sync window are stored. That's enough for the metrics, but the
database doesn't hold every open issue of a repository.

## Running it locally

You need Python 3.12, Docker and a GitHub fine-grained personal access token with read-only
access to public repositories.

```bash
git clone https://github.com/szymon-dutka/issue-pulse.git
cd issue-pulse

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # fill in GITHUB_TOKEN, POSTGRES_* and DATABASE_URL
docker compose up -d
alembic upgrade head

python -m app.jobs.run_ingest
```

The import job finds about 20 active repositories with `help wanted` issues and imports their
issues and comments. The first import of a big repository can take a few minutes.

To compute the metrics for one of them:

```python
from datetime import UTC, datetime

from app.core.database import session_scope
from app.services.metrics import get_repository_metrics

with session_scope() as session:
    print(get_repository_metrics(session, 123456789, datetime.now(UTC)))
```

The repository id is `repository_gh_id` in the `repositories` table.

## How it works

1. Discovery uses the GitHub Search API to find active, non-archived repositories with
   `help wanted` issues, split into star ranges so smaller projects are included too.
2. For each repository, the job fetches issues and comments changed since the last sync (or
   from the last 90 days on the first run) and skips pull requests.
3. Rows are upserted into PostgreSQL, so running the job again updates data instead of
   duplicating it.
4. The metrics are computed with a single SQL query per repository.

## Decisions I made

- I wrote the metrics as raw SQL (a CTE with `percentile_cont` and `COUNT(*) FILTER`) instead
  of computing them in Python. The database is better at aggregates like a median, and the
  query is short and easy to check. Everything that writes data uses SQLAlchemy.
- I exclude maintainers' own issues and require at least 10 issues. Maintainers often use
  issues as their own task list, and those say nothing about how outside contributors are
  treated. A median from two or three issues would be noise.
- Each repository is imported in its own transaction, so one failing repository doesn't undo
  the others. Rows are inserted in batches to stay under PostgreSQL's limit on parameters per
  statement.

## What's next

A FastAPI endpoint for the metrics and a list of open, unassigned issues to pick up, then a
simple web UI and deployment with a daily import.

## Contributing

Issues and pull requests are welcome. For anything bigger than a small fix, please open an
issue first so we can agree on the approach.

Tests need a separate, empty PostgreSQL database set in `TEST_DATABASE_URL` in `.env`. Before
opening a pull request, run:

```bash
ruff check .
ruff format --check .
pytest
```

## Data use

The project uses only the official GitHub REST API and respects its rate limits. It stores
metadata only (no issue or comment text, no usernames) and keeps a link to every issue on
GitHub.

Built with Python, PostgreSQL, SQLAlchemy, Alembic, Pydantic, httpx and pytest.

## License

[MIT](LICENSE)
