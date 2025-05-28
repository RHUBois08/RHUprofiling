# Renamed from custom_filters.py to report_filters.py
from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter(name='in_list')
def in_list(value, arg):
    return value in arg.split(',')
