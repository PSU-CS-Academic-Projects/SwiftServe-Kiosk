from datetime import datetime
from io import BytesIO
from pathlib import Path
import base64

import qrcode
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

from kioskapp.models import Order

def generate_queue_number():
    """Generate the next integer sequence for today's queue.

    This function is backward compatible with legacy stored values that encoded
    the date prefix into the integer (e.g. DDMMNNN). It inspects today's
    orders, extracts the 3-digit sequence portion when present, and returns the
    next sequence as an int (1,2,3...). Templates will prepend the date when
    rendering the queue display.
    """
    today = datetime.now()
    today_orders = Order.objects.filter(created_at__date=today.date()).values_list('queue_number', flat=True)

    max_seq = 0
    for q in today_orders:
        try:
            q_int = int(q)
        except Exception:
            continue
        if q_int > 999:
            seq = q_int % 1000
        else:
            seq = q_int
        if seq > max_seq:
            max_seq = seq

    next_seq = max_seq + 1
    return next_seq

def calculate_estimated_wait_time():
    """Calculate estimated wait time based on pending orders"""
    pending_orders = Order.objects.filter(status='Pending').count()
    # Assume 5 minutes per order
    estimated_minutes = pending_orders * 5
    return estimated_minutes

def generate_qr_code(order_id, amount_paid):
    """Generate QR code for order payment verification"""
    qr_data = f"ORDER:{order_id}|AMOUNT:{amount_paid}|TIME:{datetime.now().isoformat()}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64 for embedding in HTML
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    qr_image_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return f"data:image/png;base64,{qr_image_base64}"


def build_menu_image_content(source_path, output_stem=None, max_dimension=1200, quality=82):
    """Resize and compress a menu image for faster page loads."""
    source_path = Path(source_path)
    output_stem = output_stem or source_path.stem
    output_name = f"{output_stem}.jpg"

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        if image.mode in ("RGBA", "LA", "P"):
            rgba_image = image.convert("RGBA")
            background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
            background.alpha_composite(rgba_image)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)

    buffer.seek(0)
    return output_name, ContentFile(buffer.read())


def build_cropped_menu_image_content(
    source_path,
    output_stem=None,
    crop_left=0.08,
    crop_top=0.08,
    crop_right=0.92,
    crop_bottom=0.36,
    max_dimension=1200,
    quality=88,
):
    """Crop a poster-style menu image down to the food/photo area and compress it."""
    source_path = Path(source_path)
    output_stem = output_stem or source_path.stem
    output_name = f"{output_stem}.jpg"

    with Image.open(source_path) as image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size

        left = int(width * crop_left)
        top = int(height * crop_top)
        right = int(width * crop_right)
        bottom = int(height * crop_bottom)

        left = max(0, min(left, width - 1))
        top = max(0, min(top, height - 1))
        right = max(left + 1, min(right, width))
        bottom = max(top + 1, min(bottom, height))

        image = image.crop((left, top, right, bottom))
        image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        if image.mode in ("RGBA", "LA", "P"):
            rgba_image = image.convert("RGBA")
            background = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
            background.alpha_composite(rgba_image)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)

    buffer.seek(0)
    return output_name, ContentFile(buffer.read())


def get_menu_image_crop_profile(menu_name: str):
    """Return a crop profile tuned for the kind of item shown in the poster."""
    normalized = menu_name.lower()

    drink_keywords = ("coffee", "espresso", "americano", "latte", "macchiato", "cappuccino", "frappe", "tea", "milktea", "mocha")
    food_keywords = ("pasta", "lasagna", "chicken", "fries", "mojos", "bread", "bagel", "bagels", "baguette", "turon", "cake", "cheese", "ice cream", "sopas", "champorado", "chips")

    if any(keyword in normalized for keyword in drink_keywords):
        return {
            "crop_left": 0.06,
            "crop_top": 0.04,
            "crop_right": 0.94,
            "crop_bottom": 0.36,
            "max_dimension": 1200,
            "quality": 88,
        }

    if any(keyword in normalized for keyword in food_keywords):
        return {
            "crop_left": 0.05,
            "crop_top": 0.05,
            "crop_right": 0.95,
            "crop_bottom": 0.42,
            "max_dimension": 1200,
            "quality": 88,
        }

    return {
        "crop_left": 0.05,
        "crop_top": 0.05,
        "crop_right": 0.95,
        "crop_bottom": 0.40,
        "max_dimension": 1200,
        "quality": 88,
    }
