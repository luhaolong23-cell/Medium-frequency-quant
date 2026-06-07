from datetime import date


def build_job_key(job_name: str, trade_date: date) -> str:
    return f"{job_name}:{trade_date.isoformat()}"
