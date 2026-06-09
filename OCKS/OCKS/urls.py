"""
URL configuration for OCKS project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from kioskapp.views import (
    HomePageView, GetStartedView, KioskMenuView, KioskCartView, KioskCheckoutView,
    OrderCreateView, OrderStatusView, AdminOrdersDashboardView,
    add_to_cart, remove_from_cart, update_cart_item, update_order_status, update_payment_status,
    CustomerLoginView, CustomerRegisterView, customer_logout, cancel_customer_order,
    delete_customer_account
)
from kioskapp import views

urlpatterns = [
    # Admin (custom first, then built-in)
    path('admin/orders/', AdminOrdersDashboardView.as_view(), name='admin_orders'),
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='customer_login', permanent=False), name='home'),
    path('home/', views.GetStartedView.as_view(), name='home_page'),
    path('get-started/', views.GetStartedView.as_view(), name='get_started'),
    
    # Customer authentication
    path('customer/login/', CustomerLoginView.as_view(), name='customer_login'),
    path('customer/register/', CustomerRegisterView.as_view(), name='customer_register'),
    path('customer/logout/', customer_logout, name='customer_logout'),
    path('customer/delete/', delete_customer_account, name='delete_customer_account'),
    
    # Kiosk workflow
    path('kiosk/menu/', KioskMenuView.as_view(), name='kiosk_menu'),
    path('kiosk/cart/', KioskCartView.as_view(), name='kiosk_cart'),
    path('kiosk/checkout/', KioskCheckoutView.as_view(), name='kiosk_checkout'),
    path('kiosk/order/create/', OrderCreateView.as_view(), name='order_create'),
    path('kiosk/order/<int:pk>/status/', OrderStatusView.as_view(), name='order_status'),
    path('kiosk/order/<int:pk>/cancel/', cancel_customer_order, name='cancel_customer_order'),
    
    # AJAX API endpoints
    path('api/cart/add/', add_to_cart, name='add_to_cart'),
    path('api/cart/remove/', remove_from_cart, name='remove_from_cart'),
    path('api/cart/update/', update_cart_item, name='update_cart'),
    path('api/order/status/', update_order_status, name='update_order_status'),
    path('api/payment/status/', update_payment_status, name='update_payment_status'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
