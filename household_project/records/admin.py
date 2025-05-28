from django.contrib import admin
from .models import Household, Person, Family, PersonData  # Import your models here

# Register your models here
admin.site.register(Household)
admin.site.register(Person)  # Register Person model
admin.site.register(Family) 
admin.site.register(PersonData)  # Register PersonData model if it exists
