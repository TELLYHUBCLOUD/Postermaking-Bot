import uuid
import requests # Use standard requests for upload
import logging

from config import Config

UPLOAD_URL = Config.IMGBB_UPLOAD_URL

def upload_to_imgbb(image_io):
    """
    Uploads an image (BytesIO) to ImgBB via proxy.
    Returns the direct URL or None if failed.
    """
    try:
        # Reset pointer just in case
        image_io.seek(0)
        
        filename = f"{uuid.uuid4()}.jpg"
        
        # Prepare multipart upload
        # 'file' is the field name expected by the API as per the JS snippet
        files = {
            'file': (filename, image_io.read(), 'image/jpeg')
        }
        
        # Standard requests handles files kwarg perfectly
        response = requests.post(UPLOAD_URL, files=files)
        response.raise_for_status()
        
        data = response.json()
        
        if "url" in data:
            return data["url"]
        else:
            logging.error(f"Upload API returned no URL: {data}")
            return None
            
    except Exception as e:
        logging.error(f"Image Upload Failed: {e}", exc_info=True)
        return None
