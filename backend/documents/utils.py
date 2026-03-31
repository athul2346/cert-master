# qr/utils.py
import qrcode
import base64
import re
from io import BytesIO


def generate_qr_base64(url: str) -> str:
    """
    Generate QR code as base64 encoded PNG string.
    
    Args:
        url: The URL to encode in the QR code
        
    Returns:
        Base64 encoded PNG image string with data URI prefix
    """
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    qr_bytes = buffer.getvalue()
    base64_str = base64.b64encode(qr_bytes).decode('utf-8')
    return f"data:image/png;base64,{base64_str}"


def render_certificate_html(template_html, document_json, qr_verify_url):
    rendered_html = template_html

    # Replace {{key}} placeholders
    if document_json:
        for key, value in document_json.items():
            placeholder_pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            rendered_html = re.sub(placeholder_pattern, str(value), rendered_html, flags=re.IGNORECASE)

    # Generate QR code as base64
    qr_base64 = generate_qr_base64(qr_verify_url)

    # Replace the qrserver.com img src with base64 QR
    qr_pattern = r'https://api\.qrserver\.com/v1/create-qr-code/\?[^"\']*'
    rendered_html = re.sub(qr_pattern, qr_base64, rendered_html)

    # Also handle SVG lucide-qr-code if present (for other templates)
    qr_img_tag = f'<img src="{qr_base64}" alt="QR Code" style="width: 100%; height: 100%;">'
    svg_pattern = r'<svg[^>]*class="[^"]*lucide-qr-code[^"]*"[^>]*>.*?</svg>'
    rendered_html = re.sub(svg_pattern, qr_img_tag, rendered_html, flags=re.DOTALL)

    return rendered_html
