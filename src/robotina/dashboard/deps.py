"""Dashboard DB dependency.

D-01: uses the existing SessionLocal — no new engine, no new pool.
The yield-style dependency closes the session in `finally` AFTER the
TemplateResponse renders, so eager-loaded ORM rows remain bound during
template rendering (RESEARCH Pitfall 4).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from robotina.db import SessionLocal


def get_db():
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
