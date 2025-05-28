from django.urls import path
from .views import index_view, print_report_view

app_name = 'reports'

urlpatterns = [
    path('', index_view, name='index'),
    path('print/', print_report_view, name='print_report'),
]