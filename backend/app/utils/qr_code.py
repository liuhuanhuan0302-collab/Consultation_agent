import io
from qrcode import QRCode
from qrcode.constants import ERROR_CORRECT_M


def generate_qr_png(url: str, size: int = 400) -> bytes:
    qr = QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()
