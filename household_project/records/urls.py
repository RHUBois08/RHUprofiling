from django.urls import path
from .views import (
    hhForm_view, index_view, profiling_view, save_household, delete_household, save_profiling,
    remove_member, get_household_data, add_family, remove_family,
)

app_name = 'records'

urlpatterns = [
    path('', index_view, name='index'),
    path('hh_form/', hhForm_view, name='hh_form'),
    path('profiling/<str:household_number>/', profiling_view, name='profiling'),
    path('save_household/', save_household, name='save_household'),
    path('delete_household/', delete_household, name='delete_household'),
    path('save_profiling/', save_profiling, name='save_profiling'),
    path('remove-member/', remove_member, name='remove_member'),
    path('get_household_data/<str:household_number>/', get_household_data, name='get_household_data'),
    path('add_family/', add_family, name='add_family'),  # Add this line
    path('remove_family/', remove_family, name='remove_family'),  # Add this line
]