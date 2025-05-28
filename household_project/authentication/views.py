from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.conf import settings


def login_view(request):
    LOGIN_EMAIL = getattr(settings, 'LOGIN_EMAIL', None)
    LOGIN_PASSWORD = getattr(settings, 'LOGIN_PASSWORD', None)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        if email == LOGIN_EMAIL and password == LOGIN_PASSWORD:
            return redirect('dashboard:index')

        return render(request, 'authentication/login.html', {'error': 'Invalid credentials'})

    return render(request, 'authentication/login.html')

def logout_view(request):
    return redirect('login')

# Create your views here.
