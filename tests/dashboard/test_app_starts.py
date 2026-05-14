"""SPEC AC #4 / DASH-04 — the FastAPI app object exists and is importable.

This test is RED in Task 2.1 (app.py does not exist yet) and turns GREEN
in Task 2.2 once src/robotina/dashboard/app.py defines `app = FastAPI()`.
"""


def test_app_object_exists():
    from fastapi import FastAPI

    from robotina.dashboard.app import app

    assert isinstance(app, FastAPI)
