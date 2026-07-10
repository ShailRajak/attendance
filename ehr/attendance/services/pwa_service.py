import os
from django.conf import settings

def get_pwa_service_worker():
    """
    Reads sw.js from disk and returns content and content type.
    """
    path = os.path.join(
        settings.BASE_DIR, "attendance", "static", "attendance", "sw.js"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content, "application/javascript"

def get_pwa_manifest():
    """
    Reads manifest.json from disk and returns content and content type.
    """
    path = os.path.join(
        settings.BASE_DIR, "attendance", "static", "attendance", "manifest.json"
    )
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    return content, "application/json"
