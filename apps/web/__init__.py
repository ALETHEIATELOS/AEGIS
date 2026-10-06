"""AEGIS web service: project landing page + review API.

Run locally:
    pip install -e ".[web]"
    gunicorn "apps.web.app:create_app()" --bind 0.0.0.0:8000
    # or: flask --app "apps.web.app:create_app()" run

On Render: see render.yaml (Blueprint).
"""

from apps.web.app import create_app

__all__ = ["create_app"]
