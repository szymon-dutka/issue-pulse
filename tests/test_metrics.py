from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models import Issue, Repository
from app.services import metrics
from app.services.metrics import get_repository_metrics

NOW = datetime(2026, 6, 1, tzinfo=UTC)


def add_repository(session: Session) -> None:
    session.add(
        Repository(
            repository_gh_id=1,
            full_name="o/r1",
            html_url="https://github.com/o/r1",
            stargazers_count=0,
            forks_count=0,
            open_issues_count=0,
            has_issues=True,
            archived=False,
            pushed_at=NOW,
            created_at=NOW,
            repository_synced_at=NOW,
        )
    )

    session.flush()


def add_issue(
    session: Session,
    gh_id: int,
    created_at: datetime,
    *,
    response_at: datetime | None = None,
    author_association: str = "NONE",
) -> None:
    session.add(
        Issue(
            issue_gh_id=gh_id,
            repository_gh_id=1,
            issue_number=gh_id,
            title="Issue",
            html_url=f"https://github.com/o/r1/issues/{gh_id}",
            state="open",
            comments_count=0,
            author_association=author_association,
            author_type="User",
            has_assignee=False,
            labels=[],
            created_at=created_at,
            updated_at=created_at,
            first_maintainer_response_at=response_at,
        )
    )


def test_get_repository_metrics_computes_median_and_counts(db_session, monkeypatch):
    monkeypatch.setattr(metrics, "MIN_SAMPLE_SIZE", 1)

    add_repository(db_session)

    created_at = NOW - timedelta(days=10)

    add_issue(db_session, 1, created_at, response_at=created_at + timedelta(hours=1))
    add_issue(db_session, 2, created_at, response_at=created_at + timedelta(hours=3))
    add_issue(db_session, 3, created_at)

    db_session.flush()

    result = get_repository_metrics(db_session, 1, NOW)

    assert result.median_response_hours == 2.0
    assert result.responded_count == 2
    assert result.sample_size == 3


def test_get_repository_metrics_excludes_maintainer_and_old_issues(db_session, monkeypatch):
    monkeypatch.setattr(metrics, "MIN_SAMPLE_SIZE", 1)

    add_repository(db_session)

    old_created_at = NOW - timedelta(days=100)
    recent_created_at = NOW - timedelta(days=10)

    add_issue(db_session, 1, recent_created_at, response_at=recent_created_at + timedelta(hours=1))
    add_issue(
        db_session,
        2,
        recent_created_at,
        response_at=recent_created_at + timedelta(hours=1),
        author_association="OWNER",
    )
    add_issue(db_session, 3, old_created_at, response_at=old_created_at + timedelta(hours=1))

    db_session.flush()

    result = get_repository_metrics(db_session, 1, NOW)

    assert result.sample_size == 1
    assert result.responded_count == 1


def test_get_repository_metrics_computes_pickup_rate(db_session, monkeypatch):
    monkeypatch.setattr(metrics, "MIN_SAMPLE_SIZE", 1)

    add_repository(db_session)

    old_created_at = NOW - timedelta(days=60)
    recent_created_at = NOW - timedelta(days=5)

    add_issue(db_session, 1, old_created_at, response_at=old_created_at + timedelta(days=2))
    add_issue(db_session, 2, old_created_at, response_at=old_created_at + timedelta(days=40))
    add_issue(db_session, 3, old_created_at)
    add_issue(db_session, 4, recent_created_at)

    db_session.flush()

    result = get_repository_metrics(db_session, 1, NOW)

    assert result.pickup_sample_size == 3
    assert result.pickup_rate == pytest.approx(1 / 3)
    assert result.sample_size == 4


def test_get_repository_metrics_returns_none_below_min_sample(db_session):
    add_repository(db_session)

    created_at = NOW - timedelta(days=60)

    add_issue(db_session, 1, created_at, response_at=created_at + timedelta(hours=1))
    add_issue(db_session, 2, created_at, response_at=created_at + timedelta(hours=1))

    db_session.flush()

    result = get_repository_metrics(db_session, 1, NOW)

    assert result.median_response_hours is None
    assert result.pickup_rate is None
    assert result.responded_count == 2
    assert result.pickup_sample_size == 2


def test_get_repository_metrics_returns_median_at_min_sample(db_session):
    add_repository(db_session)

    created_at = NOW - timedelta(days=60)

    for gh_id in range(1, metrics.MIN_SAMPLE_SIZE + 1):
        add_issue(db_session, gh_id, created_at, response_at=created_at + timedelta(hours=1))

    db_session.flush()

    result = get_repository_metrics(db_session, 1, NOW)

    assert result.median_response_hours == 1.0
    assert result.pickup_rate == 1.0
