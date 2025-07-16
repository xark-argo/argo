import json

from apispec import APISpec
from apispec.exceptions import APISpecError
from apispec.ext.marshmallow import MarshmallowPlugin
from apispec_webframeworks.tornado import TornadoPlugin


def generate_swagger_file(handlers, file_location):
    """Automatically generates Swagger spec file based on RequestHandler
    docstrings and saves it to the specified file_location.
    """

    # Starting to generate Swagger spec file. All the relevant
    # information can be found from here https://apispec.readthedocs.io/
    spec = APISpec(
        title="Argo API",
        version="1.0.0",
        openapi_version="3.0.2",
        info={"description": "Documentation for the Argo API"},
        plugins=[TornadoPlugin(), MarshmallowPlugin()],
        servers=[
            {
                "url": "http://localhost:11636/",
                "description": "Local environment",
            },
        ],
    )
    # Looping through all the handlers and trying to register them.
    # Handlers without docstring will raise errors. That's why we
    # are catching them silently.
    for handler in handlers:
        try:
            spec.path(urlspec=handler)
        except APISpecError:
            pass

    # Write the Swagger file into specified location.
    with open(file_location, "w", encoding="utf-8") as file:
        json.dump(spec.to_dict(), file, ensure_ascii=False, indent=4)  # type: ignore[arg-type]
