from django.shortcuts import render
from django.views.generic.list import ListView
from kioskapp.models import MenuItem, Order

# Create your views here.
class HomePageView(ListView):
    model = MenuItem
    context_object_name = 'home'
    template_name = 'home.html'
    