from datetime import datetime
from io import BytesIO
from pathlib import Path
import base64

import qrcode
from PIL import Image, ImageOps
from django.core.files.base import ContentFile
from django.utils import timezone

from kioskapp.models import Order

def generate_queue_number():
    """Generate the next integer sequence for today's queue.

    This function is backward compatible with legacy stored values that encoded
    the date prefix into the integer (e.g. DDMMNNN). It inspects today's
    orders, extracts the 3-digit sequence portion when present, and returns the
    next sequence as an int (1,2,3...). Templates will prepend the date when
    rendering the queue display.
    """
    today = timezone.localdate()
    today_orders = Order.objects.filter(created_at__date=today).values_list('queue_number', flat=True)

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
    """Calculate estimated wait time based on pending and preparing orders, and item complexity"""
    active_orders = Order.objects.filter(status__in=['Pending', 'Preparing'])
    
    if not active_orders.exists():
        return 3 # base minimum wait time in minutes for a new order
        
    # Estimated preparation time in minutes by category
    PREP_TIMES = {
        'drinks': 3,
        'desserts': 2,
        'snacks': 2,
        'breads': 4,
        'pasta & noodles': 8,
        'local specialties': 8
    }
    
    total_prep_time = 0
    from kioskapp.models import OrderItem
    
    for order in active_orders:
        order_items = OrderItem.objects.filter(order=order).select_related('item', 'item__category', 'item__category__parent')
        order_max_prep = 3 # base prep time for any order is 3 mins
        for oi in order_items:
            # Get category name
            cat_name = oi.item.category.name.lower() if oi.item.category else ''
            parent_cat_name = oi.item.category.parent.name.lower() if (oi.item.category and oi.item.category.parent) else ''
            
            # Match category prep time
            prep_time = 3 # default
            for cat_key, time_val in PREP_TIMES.items():
                if cat_key in cat_name or cat_key in parent_cat_name:
                    prep_time = time_val
                    break
            
            # Since items in an order are prepared in parallel (mostly), we take the maximum item prep time
            # plus 1 minute for each additional item in the order
            total_item_prep = prep_time * oi.quantity
            if total_item_prep > order_max_prep:
                order_max_prep = total_item_prep
                
        total_prep_time += order_max_prep
        
    # Divide by 2 (assuming 2 staff members working in parallel)
    estimated_minutes = max(3, int(total_prep_time / 2))
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
