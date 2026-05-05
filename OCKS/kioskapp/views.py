from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic.list import ListView
from django.views.generic import DetailView, TemplateView
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
import json
from decimal import Decimal

from kioskapp.models import MenuItem, Order, Category, OrderItem, ItemConfiguration, Payment, DineInSettings, Customer
from kioskapp.utils import generate_queue_number, calculate_estimated_wait_time, generate_qr_code

CANCEL_WINDOW_SECONDS = 90
ALLOWED_ORDER_STATUSES = ['Pending', 'Preparing', 'Ready', 'Completed', 'Cancelled']
ALLOWED_PAYMENT_STATUSES = ['Pending', 'Paid', 'Refund Requested']


def get_customer_cancel_state(order):
    if order.status != 'Pending':
        return False, f'Cancellation is unavailable because this order is already {order.status}.'

    elapsed = int((timezone.now() - order.created_at).total_seconds())
    remaining = max(0, CANCEL_WINDOW_SECONDS - elapsed)
    if remaining <= 0:
        return False, 'Cancellation window has expired. Please contact staff for help.'

    return True, f'Eligible to cancel for the next {remaining} seconds.'


def get_order_payment_status(order):
    try:
        return order.payment.payment_status
    except Payment.DoesNotExist:
        return 'Pending'

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

        initial_cart = {}
        cart = self.request.session.get('cart', {})
        for item_id, item_data in cart.items():
            try:
                menu_item = MenuItem.objects.get(id=item_id)
            except MenuItem.DoesNotExist:
                continue

            initial_cart[str(item_id)] = {
                'name': menu_item.name,
                'price': str(menu_item.price),
                'quantity': item_data.get('quantity', 1),
                'image': menu_item.image.url if menu_item.image else '',
                'customizations': item_data.get('customizations', []),
            }

        context['initial_cart'] = initial_cart
        return context


class GetStartedView(TemplateView):
    """Landing page with a rotating carousel of menu images and a Get Started button"""
    template_name = 'get_started.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # pick up to 6 menu items (prefer ones with images)
        items_with_images = list(MenuItem.objects.filter(available=True).exclude(image='').select_related('category')[:6])
        if len(items_with_images) < 6:
            # fill the rest with any available items
            ids = [i.id for i in items_with_images]
            more = list(MenuItem.objects.filter(available=True).exclude(id__in=ids).select_related('category')[:6 - len(items_with_images)])
            items_with_images.extend(more)

        customer_id = self.request.session.get('customer_id')
        my_orders = Order.objects.none()
        if customer_id:
            my_orders = Order.objects.filter(customer_id=customer_id).select_related('payment').order_by('-created_at')[:6]
            for order in my_orders:
                can_cancel, cancel_note = get_customer_cancel_state(order)
                payment_status = get_order_payment_status(order)
                order.can_customer_cancel = can_cancel
                order.cancel_note = cancel_note
                order.payment_status_value = payment_status
                if payment_status.lower() == 'paid':
                    order.refund_note = 'If cancelled, payment will be marked as Refund Requested for staff processing.'
                else:
                    order.refund_note = 'Pending payments can be cancelled immediately within the allowed window.'

        context['carousel_items'] = items_with_images
        context['my_orders'] = my_orders
        context['show_welcome_card'] = self.request.session.pop('show_welcome_card', False)
        context['customer_name'] = self.request.session.get('customer_name', '')
        context['cancel_feedback'] = self.request.session.pop('cancel_feedback', None)
        context['cancel_window_seconds'] = CANCEL_WINDOW_SECONDS
        return context
    
    def get(self, request, *args, **kwargs):
        # Require customer to be logged in
        if not request.session.get('customer_id'):
            return redirect('customer_login')
        
        # Clear any existing cart when starting a new kiosk session
        request.session.pop('cart', None)
        return super().get(request, *args, **kwargs)

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
        dine_in_settings = DineInSettings.objects.first()
        if dine_in_settings is None:
            dine_in_settings = DineInSettings(is_available=True, estimated_wait_minutes=0, max_party_size=8)

        context['dine_in_available'] = dine_in_settings.is_available
        context['dine_in_wait_minutes'] = dine_in_settings.estimated_wait_minutes
        context['dine_in_max_party_size'] = dine_in_settings.max_party_size
        context['checkout_error'] = self.request.session.pop('checkout_error', None)
        return context

class OrderCreateView(TemplateView):
    """Create an order from cart session"""
    template_name = 'kiosk_receipt.html'
    
    def post(self, request, *args, **kwargs):
        cart = request.session.get('cart', {})
        order_type = request.POST.get('order_type')
        payment_method = request.POST.get('payment_method')
        party_size_raw = request.POST.get('party_size')
        
        if not cart or not order_type:
            return redirect('kiosk_menu')

        party_size = None
        if order_type == 'dine_in':
            dine_in_settings = DineInSettings.objects.first()
            dine_in_available = dine_in_settings.is_available if dine_in_settings else True
            max_party_size = dine_in_settings.max_party_size if dine_in_settings else 8

            if not dine_in_available:
                request.session['checkout_error'] = 'Dine-in is currently full. Please choose Take Out or Delivery.'
                return redirect('kiosk_checkout')

            if not party_size_raw:
                request.session['checkout_error'] = 'Please select party size for dine-in.'
                return redirect('kiosk_checkout')

            try:
                party_size = int(party_size_raw)
            except (TypeError, ValueError):
                request.session['checkout_error'] = 'Invalid party size selected.'
                return redirect('kiosk_checkout')

            if party_size < 1 or party_size > max_party_size:
                request.session['checkout_error'] = f'Party size must be between 1 and {max_party_size}.'
                return redirect('kiosk_checkout')
        
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
        queue_seq = generate_queue_number()
        
        # Get customer if logged in
        customer = None
        customer_id = request.session.get('customer_id')
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
            except Customer.DoesNotExist:
                pass
        
        order = Order.objects.create(
            order_type=order_type,
            total_price=total_price,
            party_size=party_size,
            queue_number=queue_seq,
            status='Pending',
            customer=customer
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
            'cancel_window_seconds': CANCEL_WINDOW_SECONDS,
            'refund_note': 'If payment is marked Paid before cancellation, status will move to Refund Requested for staff processing.',
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
        payment_status_value = context['payment'].payment_status.lower()
        context['show_track_qr'] = (payment_status_value == 'pending' and order.status != 'Cancelled')
        context['track_qr_code'] = generate_qr_code(order.id, order.total_price) if context['show_track_qr'] else None
        can_cancel, cancel_note = get_customer_cancel_state(order)
        context['can_customer_cancel'] = can_cancel
        context['cancel_note'] = cancel_note
        if payment_status_value == 'paid':
            context['refund_note'] = 'If you cancel now, payment will be marked as Refund Requested.'
        else:
            context['refund_note'] = 'Pending payments can be cancelled immediately if eligible.'
        return context

@method_decorator(staff_member_required, name='dispatch')
class AdminOrdersDashboardView(TemplateView):
    """Admin dashboard for order management"""
    template_name = 'admin_orders_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status_filter = self.request.GET.get('status', '')
        payment_status_filter = self.request.GET.get('payment_status', '')
        search_query = self.request.GET.get('search', '').strip()
        page_number = self.request.GET.get('page', 1)
        
        orders_query = Order.objects.select_related('payment', 'customer').all().order_by('-created_at')
        
        if status_filter:
            orders_query = orders_query.filter(status=status_filter)
        if payment_status_filter:
            orders_query = orders_query.filter(payment__payment_status__iexact=payment_status_filter)
        if search_query:
            search_filter = (
                Q(order_type__icontains=search_query) |
                Q(status__icontains=search_query) |
                Q(payment__method__icontains=search_query) |
                Q(payment__payment_status__icontains=search_query) |
                Q(orderitem__item__name__icontains=search_query)
            )
            if search_query.isdigit():
                search_filter |= Q(id=int(search_query)) | Q(queue_number=int(search_query))
            orders_query = orders_query.filter(search_filter).distinct()

        paginator = Paginator(orders_query, 12)
        page_obj = paginator.get_page(page_number)

        context['orders'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['is_paginated'] = page_obj.has_other_pages()
        context['pending_count'] = Order.objects.filter(status='Pending').count()
        context['preparing_count'] = Order.objects.filter(status='Preparing').count()
        context['ready_count'] = Order.objects.filter(status='Ready').count()
        context['completed_count'] = Order.objects.filter(status='Completed').count()
        context['statuses'] = ALLOWED_ORDER_STATUSES
        context['payment_statuses'] = ALLOWED_PAYMENT_STATUSES
        context['selected_payment_status'] = payment_status_filter
        context['search_query'] = search_query
        return context

@require_POST
def add_to_cart(request):
    """AJAX endpoint to add item to cart"""
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        quantity = int(data.get('quantity', 1))
        customizations = data.get('customizations', [])
        
        cart = request.session.get('cart', {})
        # enforce per-item max_quantity
        try:
            menu_item = MenuItem.objects.get(id=item_id)
            max_q = int(menu_item.max_quantity or 99)
        except MenuItem.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Item not found'}, status=404)

        key = str(item_id)
        existing_qty = cart.get(key, {}).get('quantity', 0)
        new_qty = min(existing_qty + quantity, max_q)
        if new_qty <= 0:
            if key in cart:
                del cart[key]
        else:
            cart[key] = {
                'quantity': new_qty,
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
def update_cart_item(request):
    """AJAX endpoint to update item quantity"""
    try:
        data = json.loads(request.body)
        item_id = str(data.get('item_id'))
        quantity = int(data.get('quantity', 1))
        
        cart = request.session.get('cart', {})
        if item_id in cart:
            # enforce per-item max_quantity
            try:
                menu_item = MenuItem.objects.get(id=int(item_id))
                max_q = int(menu_item.max_quantity or 99)
            except MenuItem.DoesNotExist:
                max_q = 99

            if quantity <= 0:
                del cart[item_id]
            else:
                cart[item_id]['quantity'] = min(quantity, max_q)
            request.session['cart'] = cart
        
        return JsonResponse({
            'success': True,
            'cart_count': len(cart),
            'message': 'Cart updated'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@staff_member_required
@require_POST
def update_order_status(request):
    """AJAX endpoint to update order status (admin)"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('status')

        if new_status not in ALLOWED_ORDER_STATUSES:
            return JsonResponse({'success': False, 'error': 'Invalid order status'}, status=400)
        
        order = get_object_or_404(Order, id=order_id)
        order.status = new_status
        order.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Order status updated to {new_status}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@staff_member_required
@require_POST
def update_payment_status(request):
    """AJAX endpoint to update payment status (admin)"""
    try:
        data = json.loads(request.body)
        order_id = data.get('order_id')
        new_status = data.get('payment_status')

        if new_status not in ALLOWED_PAYMENT_STATUSES:
            return JsonResponse({'success': False, 'error': 'Invalid payment status'}, status=400)

        order = get_object_or_404(Order, id=order_id)
        payment = get_object_or_404(Payment, order=order)
        payment.payment_status = new_status
        payment.save()

        return JsonResponse({
            'success': True,
            'message': f'Payment status updated to {new_status}'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


class CustomerLoginView(TemplateView):
    """Customer login view"""
    template_name = 'customer_login.html'
    
    def post(self, request, *args, **kwargs):
        phone_or_email = request.POST.get('phone_or_email', '').strip()
        
        if not phone_or_email:
            return render(request, self.template_name, {
                'error': 'Please enter a phone number or email'
            })
        
        try:
            # Try to find customer by phone number or email
            customer = Customer.objects.filter(
                Q(phone_number=phone_or_email) | Q(email=phone_or_email)
            ).first()
            
            if not customer:
                return render(request, self.template_name, {
                    'error': 'No customer found with that phone/email. Please register first.'
                })
            
            # Store customer in session
            request.session['customer_id'] = customer.id
            request.session['customer_name'] = customer.name
            request.session['customer_phone'] = customer.phone_number
            request.session['show_welcome_card'] = True
            
            return redirect('get_started')
        except Exception as e:
            return render(request, self.template_name, {
                'error': f'Login error: {str(e)}'
            })


class CustomerRegisterView(TemplateView):
    """Customer registration view"""
    template_name = 'customer_register.html'
    
    def post(self, request, *args, **kwargs):
        name = request.POST.get('name', '').strip()
        phone_number = request.POST.get('phone_number', '').strip()
        email = request.POST.get('email', '').strip()
        
        errors = {}
        
        if not name:
            errors['name'] = 'Name is required'
        if not phone_number:
            errors['phone_number'] = 'Phone number is required'
        
        if errors:
            context = {
                'errors': errors,
                'name': name,
                'phone_number': phone_number,
                'email': email
            }
            return render(request, self.template_name, context)
        
        try:
            # Check if customer already exists
            if Customer.objects.filter(phone_number=phone_number).exists():
                return render(request, self.template_name, {
                    'errors': {'phone_number': 'This phone number is already registered'},
                    'name': name,
                    'phone_number': phone_number,
                    'email': email
                })
            
            if email and Customer.objects.filter(email=email).exists():
                return render(request, self.template_name, {
                    'errors': {'email': 'This email is already registered'},
                    'name': name,
                    'phone_number': phone_number,
                    'email': email
                })
            
            # Create new customer
            customer = Customer.objects.create(
                name=name,
                phone_number=phone_number,
                email=email if email else None
            )
            
            # Store customer in session
            request.session['customer_id'] = customer.id
            request.session['customer_name'] = customer.name
            request.session['customer_phone'] = customer.phone_number
            request.session['show_welcome_card'] = True
            
            return redirect('get_started')
        except Exception as e:
            return render(request, self.template_name, {
                'errors': {'general': f'Registration error: {str(e)}'},
                'name': name,
                'phone_number': phone_number,
                'email': email
            })


def customer_logout(request):
    """Logout customer and clear session"""
    request.session.pop('customer_id', None)
    request.session.pop('customer_name', None)
    request.session.pop('customer_phone', None)
    return redirect('home')


@require_POST
def cancel_customer_order(request, pk):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('customer_login')

    order = get_object_or_404(Order, id=pk, customer_id=customer_id)
    can_cancel, cancel_note = get_customer_cancel_state(order)
    if not can_cancel:
        request.session['cancel_feedback'] = {
            'type': 'warning',
            'text': cancel_note,
        }
        return redirect('home_page')

    order.status = 'Cancelled'
    order.save(update_fields=['status'])

    refund_note = ''
    try:
        payment = order.payment
        if payment.payment_status.lower() == 'paid':
            payment.payment_status = 'Refund Requested'
            payment.save(update_fields=['payment_status'])
            refund_note = ' Payment has been marked as Refund Requested.'
    except Payment.DoesNotExist:
        pass

    request.session['cancel_feedback'] = {
        'type': 'success',
        'text': f'Order #{order.id} was cancelled successfully.{refund_note}',
    }
    return redirect('home_page')