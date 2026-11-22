from pydantic import BaseModel


class RepositoryMetrics(BaseModel):
    median_response_hours: float | None
    responded_count: int
    sample_size: int
    pickup_rate: float | None
    pickup_sample_size: int
