import logging

from utils import log  # noqa: F401  # isort: skip
import tornado.web
from swagger_ui import api_doc

from configs.parser import setup_parser
from configs.settings import APP_SETTINGS
from core.i18n.translation import translation_loader
from database import db, vector
from database.migration import run_online_migrations
from events import event_handlers  # noqa: F401
from handlers.router import api_router
from init_swagger import generate_swagger_file
from services import model_provider
from services.auth import auth_service as auth
from services.doc import document_process
from services.model import model_download, popular_model, sync_ollama
from services.tool import mcp_init, mcp_tool_install
from utils.path import app_path

SWAGGER_API_OUTPUT_FILE = app_path("templates", "swagger.json")


def initialize_components():
    """Initialize all service modules and dependencies."""
    translation_loader.init()
    model_provider.initialize_provider_settings()
    mcp_init.init()
    db.init()
    auth.initialize_default_user()
    vector.init()
    popular_model.init()
    model_download.init()
    document_process.init()
    sync_ollama.init()
    mcp_tool_install.init()


def create_app() -> tornado.web.Application:
    """Create and configure the Tornado application instance."""
    initialize_components()

    handlers = api_router.get_routes()
    app = tornado.web.Application(handlers=handlers, default_host=None, transforms=None, **APP_SETTINGS)

    # Generate Swagger specification
    generate_swagger_file(handlers=handlers, file_location=SWAGGER_API_OUTPUT_FILE)

    # Mount Swagger UI
    api_doc(
        app,
        config_path=SWAGGER_API_OUTPUT_FILE,
        url_prefix="/api/swagger/doc",
        title="LLM Agent API Docs",
    )

    return app


def run_server(host: str, port: int):
    """Start the Tornado HTTP server."""
    app = create_app()
    try:
        app.listen(port, host)
        logging.info(f"Server started at http://{host}:{port}")
        tornado.ioloop.IOLoop.current().start()
    except Exception:
        logging.exception("Failed to start the server.")
    finally:
        logging.info("Server shut down.")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    parser = setup_parser()
    args = parser.parse_args()
    logging.info(f"Startup arguments: {args}")

    run_online_migrations()

    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
