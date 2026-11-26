from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.metrics import RepositoryMetrics
from app.services.ingest import MAINTAINER_ASSOCIATIONS

RESPONSE_WINDOW = timedelta(days=90)
PICKUP_WINDOW = timedelta(days=30)
MIN_SAMPLE_SIZE = 10

REPOSITORY_METRICS_QUERY = text(
    """
    WITH sample AS (
        SELECT created_at, first_maintainer_response_at
        FROM issues
        WHERE repository_gh_id = :repository_gh_id
          AND created_at >= :window_start
          AND author_association <> ALL(:maintainer_associations)
    )
    SELECT
        percentile_cont(0.5) WITHIN GROUP (
            ORDER BY EXTRACT(EPOCH FROM first_maintainer_response_at - created_at) / 3600
        ) AS median_hours,
        COUNT(first_maintainer_response_at) AS responded,
        COUNT(*) AS total,
        COUNT(*) FILTER (
            WHERE created_at < :pickup_cutoff
              AND first_maintainer_response_at <= created_at + :pickup_window
        ) AS picked_up,
        COUNT(*) FILTER (WHERE created_at < :pickup_cutoff) AS pickup_total
    FROM sample
    """
)


def get_repository_metrics(
    session: Session, repository_gh_id: int, now: datetime
) -> RepositoryMetrics:
    window_start = now - RESPONSE_WINDOW
    pickup_cutoff = now - PICKUP_WINDOW

    row = session.execute(
        REPOSITORY_METRICS_QUERY,
        {
            "repository_gh_id": repository_gh_id,
            "window_start": window_start,
            "pickup_cutoff": pickup_cutoff,
            "pickup_window": PICKUP_WINDOW,
            "maintainer_associations": list(MAINTAINER_ASSOCIATIONS),
        },
    ).one()

    median_response_hours = row.median_hours if row.responded >= MIN_SAMPLE_SIZE else None

    pickup_rate = row.picked_up / row.pickup_total if row.pickup_total >= MIN_SAMPLE_SIZE else None

    return RepositoryMetrics(
        median_response_hours=median_response_hours,
        responded_count=row.responded,
        sample_size=row.total,
        pickup_sample_size=row.pickup_total,
        pickup_rate=pickup_rate,
    )
