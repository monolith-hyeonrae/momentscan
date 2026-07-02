"""momentscan_worker — single-file processing harness over visualstack.

A worker process picks one input video, runs it through the
visualstack pipeline, and writes parquet output. Designed to live
under a job-queue orchestrator (RQ / Celery / Postgres-as-queue) that
spawns these as subprocesses with arguments / env supplied per job.

Public entry point:
    run_job(job: Job) -> JobResult
"""

from momentscan_worker.service import Job, JobResult, run_job

__all__ = ["Job", "JobResult", "run_job"]
__version__ = "0.0.0"
