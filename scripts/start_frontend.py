import sys
from pathlib import Path

from streamlit.web import cli as streamlit_cli

from frontend.config import get_frontend_settings


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    settings = get_frontend_settings()
    sys.argv = [
        "streamlit",
        "run",
        str(ROOT / "frontend" / "app.py"),
        f"--server.address={settings.host}",
        f"--server.port={settings.port}",
    ]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    main()
