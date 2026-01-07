# qr/utils.py
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile

def generate_qr_image(url: str):
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    return ContentFile(buffer.getvalue(), name="qr.png")
