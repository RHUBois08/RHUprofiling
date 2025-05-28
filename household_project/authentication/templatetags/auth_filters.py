# Renamed from custom_filters.py to auth_filters.py

from django import template

register = template.Library()

@register.filter
def in_list(value, list_str):
    return value in list_str.split(',')
