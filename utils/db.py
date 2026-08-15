"""
Backward-compatible re-export of the database wrapper.

New code should import from :mod:`core.database` directly:
    from core.database import db
This module keeps the old ``from utils.db import db`` working.
"""
from core.database import Database, db  # noqa: F401
