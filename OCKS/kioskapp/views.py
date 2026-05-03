from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.list import ListView
from django.views.generic import DetailView, TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from decimal import Decimal

from kioskapp.models import MenuItem, Order, Category, OrderItem, ItemConfiguration, Payment
from kioskapp.utils import generate_queue_number, calculate_estimated_wait_time, generate_qr_code

# Create your views here.

class HomePageView(ListView):
    model = MenuItem
    context_object_name = 'home'
    template_name = 'home.html'

class KioskMenuView(TemplateView):
    """Display menu items for kiosk ordering"""
    template_name = 'kiosk_menu.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        context['menu_items'] = MenuItem.objects.filter(available=True).select_related('category')
        return context

class KioskCartView(TemplateView):
    """Handle kiosk cart display and management"""
    template_name = 'kiosk_cart.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = self.request.session.get('cart', {})
        cart_items = []
        total = Decimal('0.00')
        
        for item_id, item_data in cart.items():
            try:
                menu_item = MenuItem.objects.get(id=item_id)
                item_total = menu_item.price * item_data['quantity']
                cart_items.append({
                    'menu_item': menu_item,
                    'quantity': item_data['quantity'],
                    'subtotal': item_total,
                    'customizations': item_data.get('customizations', [])
                })
                total += item_total
            except MenuItem.DoesNotExist:
                pass
        
        context['cart_items'] = cart_items
        context['cart_total'] = total
        context['cart_empty'] = len(cart_items) == 0
        return context

class KioskCheckoutView(TemplateView):
    """Handle order type selection and checkout"""
    template_name = 'kiosk_checkout.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = self.request.session.get('cart', {})
        total = Decimal('0.00')
        
        for item_id, item_data in cart.items():
            try:
                menu_item = MenuItem.objects.get(id=item_id)
                total += menu_item.price * item_data['quantity']
            except MenuItem.DoesNotExist:
                pass
        
        context['cart_total'] = total
        context['order_types'] = Order.ORDER_TYPE
        context['payment_methods'] = Payment.PAYMENT_METHODS
        return context

class OrderCreateView(TemplateView):
    """Create an order from cart session"""
    template_name = 'kiosk_receipt.html'
    
    def post(self, request, *args, **kwargs):
        cart = request.session.get('cart', {})
        order_type = request.POST.get('order_type')
        payment_method = request.POST.get('payment_method')
        
        if not cart or not order_type:
            return redirect('kiosk_menu')
        
        # Calculate total
        total_price = Decimal('0.00')
        cart_items_data = []
        
        for item_id, item_data in cart.items():
            try:
                menu_item = MenuItem.objects.get(id=item_id)
                item_total = menu_item.price * item_data['quantity']
                total_price += item_total
                cart_items_data.append({
                    'menu_item': menu_item,
                    'quantity': item_data['quantity'],
                    'subtotal': item_total,
                    'customizations': item_data.get('customizations', [])
                })
            except MenuItem.DoesNotExist:
                pass
        
        # Create order
        queue_number = generate_queue_number()
        order = Order.objects.create(
            order_type=order_type,
            total_price=total_price,
            queue_number=int(queue_number.split('-')[1]),
            status='Pending'
        )
        
        # Add order items
        for item_data in cart_items_data:
            order_item = OrderItem.objects.create(
                order=order,
                item=item_data['menu_item'],
                quantity=item_data['quantity'],
                subtotal=item_data['subtotal']
            )
            
            # Add customizations
            for customization in item_data['customizations']:
                ItemConfiguration.objects.create(
                    order_item=order_item,
                    option_name=customization['name'],
                    option_value=customization['value']
                )
        
        # Create payment record
        payment = Payment.objects.create(
            order=order,
            method=payment_method or 'cash',
            amount_paid=total_price,
            payment_status='Pending'
        )
        
        # Generate QR code
        qr_code = generate_qr_code(order.id, total_price)
        
        # Clear cart
        request.session.pop('cart', None)
        
        # Get estimated wait time
        estimated_wait = calculate_estimated_wait_time()
        
        # Calculate tax (12%)
        tax_amount = total_price * Decimal('0.12')
        total_with_tax = total_price + tax_amount
        
        context = {
            'order': order,
            'order_items': OrderItem.objects.filter(order=order).select_related('item'),
            'payment': payment,
            'qr_code': qr_code,
            'estimated_wait': estimated_wait,
            'tax_amount': tax_amount,
            'total_with_tax': total_with_tax,
        }
        
        return render(request, self.template_name, context)

class OrderStatusView(DetailView):
    """Display order status and details"""
    model = Order
    template_name = 'kiosk_status.html'
    context_object_name = 'order'
    pk_url_kwarg = 'pk'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        context['order_items'] = OrderItem.objects.filter(order=order).select_related('item')
        context['estimated_wait'] = calculate_estimated_wait_time()
        context['payment'] = Payment.objects.get(order=order)
        return context

class AdminOrdersDashboardView(TemplateView):
    """Admin dashboard for order management"""
    template_name = 'admin_orders_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_filter = self.request.GET.get('status', '')
        
        orders_query = Order.objects.all().order_by('-created_at')
        
        if status_filter:
            orders_query = orders_query.filter(status=status_filter)
        
        context['orders'] = orders_query
        context['pending_count'] = Order.objects.filter(status='Pending').count()
        context['preparing_count'] = Order.objects.filter(status='Preparing').count()
        context['ready_count'] = Order.objects.filter(status='Ready').count()
        context['statuses'] = ['Pending', 'Preparing', 'Ready', 'Completed']
        return context

@require_POST
@csrf_exempt
def add_to_cart(request):
    """AJAX endpoint to add item to cart"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        customizations = data.get('customizations', [])
        
        cart = request.session.get('cart', {})
        
        if str(item_id) in cart:
            cart[str(item_id)]['quantity'] += quantity
        else:
            cart[str(item_id)] = {
                'quantity': quantity,
                'customizations': customizations
            }
        
        request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'message': 'Item added to cart'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@csrf_exempt
def remove_from_cart(request):
    """AJAX endpoint to remove item from cart"""
    try:
        data = json.loads(request.body)
        item_id = str(data.get('item_id'))
        
        cart = request.session.get('cart', {})
        
        if item_id in cart:
            del cart[item_id]
            request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'message': 'Item removed from cart'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@csrf_exempt
def update_cart_item(request):
    """AJAX endpoint to update item quantity"""
    try:
        data = json.loads(request.body)
        item_id = str(data.get('item_id'))
        quantity = int(data.get('quantity', 1))
        
        cart = request.session.get('cart', {})
        
        if item_id in cart:
            if quantity <= 0:
                del cart[item_id]
            else:
                cart[item_id]['quantity'] = quantity
            request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'message': 'Cart updated'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@csrf_exempt
def update_order_status(request):
    """AJAX endpoint to update order status (admin)"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')
        
        order = get_object_or_404(Order, id=order_id)
        order.status = new_status
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Order status updated to {new_status}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)