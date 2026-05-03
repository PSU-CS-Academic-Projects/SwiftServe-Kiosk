from datetime import datetime
from io import BytesIO
import qrcode
from django.core.files.base import ContentFile
from kioskapp.models import Order
import base64

def generate_queue_number():
    """Generate a unique queue number based on today's date and current order count"""
    today = datetime.now().strftime("%d%m")  # DDMM format
    today_orders = Order.objects.filter(created_at__date=datetime.now().date()).count()
    queue_num = today_orders + 1
    return f"Q-{today}{queue_num:03d}"

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
