import logging
from typing import Any, Optional, Union

from tornado.web import RequestHandler, url


class APIRouter:
    def __init__(self):
        self.routes: list = []
        self._logger = logging.getLogger("APIRouter")
        self._logger.setLevel(logging.INFO)

    def add(
        self,
        pattern: str,
        handler: type[RequestHandler],
        kwargs: Optional[dict[str, Any]] = None,
        name: Optional[str] = None,
    ):
        if not pattern.startswith("/"):
            self._logger.warning(f"Route pattern should start with '/': {pattern}")
            pattern = "/" + pattern

        self._logger.info(f"Register route: {pattern} -> {handler.__name__} (name={name})")
        self.routes.append(url(pattern, handler, kwargs=kwargs or {}, name=name))

    def include(self, route_list: list):
        self._logger.info(f"Including {len(route_list)} external routes")
        self.routes.extend(route_list)

    def get_routes(self) -> list:
        return self.routes

    def group(
        self,
        prefix: str,
        routes: list[
            Union[
                tuple[str, type[RequestHandler]],
                tuple[str, type[RequestHandler], Optional[dict[str, Any]]],
                tuple[str, type[RequestHandler], Optional[dict[str, Any]], Optional[str]],
            ]
        ],
        group_kwargs: Optional[dict[str, Any]] = None,
    ):
        if not prefix.startswith("/"):
            prefix = "/" + prefix
        if not prefix.endswith("/"):
            prefix += "/"

        for route in routes:
            if len(route) < 2:
                raise ValueError("Each route tuple must have at least pattern and handler")

            pattern = route[0].lstrip("/")
            handler = route[1]
            kwargs = None
            name = None

            if len(route) >= 3:
                kwargs = route[2]
            if len(route) == 4:
                name = route[3]

            merged_kwargs = dict(group_kwargs or {})
            if kwargs:
                if not isinstance(kwargs, dict):
                    raise TypeError(f"Expected kwargs to be dict, got {type(kwargs).__name__}")
                merged_kwargs.update(kwargs)

            full_pattern = prefix + pattern
            self.add(full_pattern, handler, kwargs=merged_kwargs, name=name)


api_router = APIRouter()
