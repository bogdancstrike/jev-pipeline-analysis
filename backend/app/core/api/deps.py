from typing import Annotated

from fastapi import Depends, Request

from ..errors import NotFound
from ..pipeline import Job
from ..platform import Platform


def get_platform(request: Request) -> Platform:
    return request.app.state.platform


PlatformDep = Annotated[Platform, Depends(get_platform)]


def get_job(job_id: str, platform: PlatformDep) -> Job:
    job = platform.jobs.get(job_id)
    if job is None:
        raise NotFound("job not found (expired, deleted or never existed)")
    return job


JobDep = Annotated[Job, Depends(get_job)]
