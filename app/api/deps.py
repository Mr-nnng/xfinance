"""HTTP dependency wiring."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request

from ..services.context import AppCore, Services, iter_services


def get_services(request: Request) -> Iterator[Services]:
    core: AppCore = request.app.state.core
    yield from iter_services(core)


ServicesDep = Annotated[Services, Depends(get_services)]
