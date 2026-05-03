from django.db import models

# Create your models here.
class Order(models.Model):
    ORDER_TYPE = [
        ('take_out', 'Take Out'),
        ('dine_in', 'Dine In'),
        ('delivery', 'Delivery'),
    ]

    order_type = models.CharField(max_length=10, choices=ORDER_TYPE)
    total_price = models.DecimalField(max_digits=8, decimal_places=2)
    queue_number = models.IntegerField()
    status = models.CharField(max_length=20, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

class Category(models.Model):
    name = models.CharField(max_length=100)

class MenuItem(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='menu_items/', blank=True, null=True)
    max_quantity = models.PositiveIntegerField(default=99)
    available = models.BooleanField(default=True)

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    subtotal = models.DecimalField(max_digits=8, decimal_places=2)

class ItemConfiguration(models.Model):
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    option_name = models.CharField(max_length=100)
    option_value = models.CharField(max_length=100)

class Payment(models.Model):
    PAYMENT_METHODS = [
        ('cash', 'Cash'),
        ('gcash', 'GCash'),
        ('card', 'Card'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    method = models.CharField(max_length=10, choices=PAYMENT_METHODS)
    amount_paid = models.DecimalField(max_digits=8, decimal_places=2)
    payment_status = models.CharField(max_length=20, default="Pending")
    paid_at = models.DateTimeField(auto_now_add=True)