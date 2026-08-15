"""
Image upload helper (ImgBB proxy).
"""
import uuid
import logging

import requests

from config import Config

logger = logging.getLogger(__name__)

UPLOAD_URL = Config.IMGBB_UPLOAD_URL


def upload_to_imgbb(image_io):
    """Upload an image BytesIO to ImgBB via proxy. Returns URL or None."""
    try:
        image_io.seek(0)
        filename = f"{uuid.uuid4()}.jpg"
        files = {"file": (filename, image_io.read(), "image/jpeg")}
        response = requests.post(UPLOAD_URL, files=files, timeout=30)
        response.raise_for_status()
        data = response.json()
        if "url" in data:
            return data["url"]
        logger.error(f"Upload API returned no URL: {data}")
        return None
    except Exception as e:
        logger.error(f"Image Upload Failed: {e}", exc_info=True)
        return None
