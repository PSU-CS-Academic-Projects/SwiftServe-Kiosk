from django.contrib import admin
from kioskapp.models import Order, Category, MenuItem, OrderItem, ItemConfiguration, Payment

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'available', 'max_quantity', 'has_image')
    list_filter = ('category', 'available')
    search_fields = ('name', 'description')
    fields = ('name', 'category', 'price', 'description', 'image', 'max_quantity', 'available')
    
    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = 'Has Image'

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    fields = ('item', 'quantity', 'subtotal')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('queue_number', 'order_type', 'status', 'total_price', 'created_at')
    list_filter = ('status', 'order_type', 'created_at')
    search_fields = ('queue_number',)
    readonly_fields = ('created_at', 'queue_number')
    fieldsets = (
        ('Order Info', {'fields': ('queue_number', 'order_type', 'total_price')}),
        ('Status', {'fields': ('status',)}),
        ('Timestamps', {'fields': ('created_at',)}),
    )
    inlines = [OrderItemInline]

@admin.register(ItemConfiguration)
class ItemConfigurationAdmin(admin.ModelAdmin):
    list_display = ('order_item', 'option_name', 'option_value')
    list_filter = ('option_name',)

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'method', 'payment_status', 'amount_paid', 'paid_at')
    list_filter = ('method', 'payment_status', 'paid_at')
    readonly_fields = ('paid_at',)
