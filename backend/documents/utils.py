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


def render_certificate_html(template_html: str, document_json: dict, qr_verify_url: str) -> str:
    """
    Render certificate HTML by replacing placeholders and adding QR code.
    
    Args:
        template_html: HTML template string with {{placeholder}} syntax
        document_json: Dictionary of key-value pairs for replacement
        qr_verify_url: URL to encode in the QR code
        
    Returns:
        Fully rendered HTML string with placeholders replaced and QR code embedded
    """
    rendered_html = template_html
    
    # 1. Replace {{key}} placeholders with document_json values
    if document_json:
        for key, value in document_json.items():
            # Replace {{key}} with value (case-insensitive matching)
            placeholder_pattern = r'\{\{\s*' + re.escape(key) + r'\s*\}\}'
            rendered_html = re.sub(placeholder_pattern, str(value), rendered_html, flags=re.IGNORECASE)
    
    # 2. Generate QR code as base64
    qr_base64 = generate_qr_base64(qr_verify_url)
    
    # 3. Replace QR SVG placeholder with base64 img tag
    # The QR placeholder is an SVG with class "lucide-qr-code"
    qr_img_tag = f'<img src="{qr_base64}" alt="QR Code" style="width: 100%; height: 100%;">'
    
    # Replace the SVG QR code element with the img tag
    # Match svg element with lucide-qr-code class
    svg_pattern = r'<svg[^>]*class="[^"]*lucide-qr-code[^"]*"[^>]*>.*?</svg>'
    rendered_html = re.sub(svg_pattern, qr_img_tag, rendered_html, flags=re.DOTALL)
    
    return rendered_html
