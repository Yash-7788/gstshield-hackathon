"""Run with python -m app; launch settings cannot silently diverge from .env."""

import sys

import uvicorn

from app.config import ConfigurationError, load_settings
from app.main import create_app


def main() -> int:
    try:
        settings = load_settings()
        application = create_app(settings)
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    # ponytail: one local worker for this hackathon; revisit with an explicit hosting change.
    # No reload creates a second process or unexpectedly resets jobs.
    uvicorn.run(
        application,
        host=settings.host,
        port=settings.port,
        workers=1,
        log_level=settings.log_level.lower(),
        access_log=False,  # URLs may eventually contain bearer download capabilities.
        proxy_headers=False,
        server_header=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
