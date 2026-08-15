"""
Backward-compatible re-export of the upload helper.

New code should import from :mod:`services.upload`.
"""
from services.upload import upload_to_imgbb  # noqa: F401
