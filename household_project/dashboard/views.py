from datetime import datetime
from django.shortcuts import render
from records.models import Household, Person, PersonData
from django.db import models
from django.db.models import Count, Q
import json  # Add this import
from django.contrib.auth.decorators import login_required

# @login_required
def index_view(request):
    current_year = datetime.now().year
    
    selected_barangay = request.GET.get('barangay', '')  # Get the selected Barangay from the request
    selected_year = int(request.GET.get('year', current_year))  # Ensure selected_year is an integer
    year_range = range(2025, current_year + 6)

    # Filter PersonData by year and join with Person
    person_data = PersonData.objects.filter(year=selected_year).select_related('person')

    households = Household.objects.filter(
        barangay__icontains=selected_barangay
    ).count() if selected_barangay else Household.objects.count()

    families = Household.objects.filter(
        barangay__icontains=selected_barangay
    ).prefetch_related('families').aggregate(total_families=models.Count('families')) if selected_barangay else Household.objects.prefetch_related('families').aggregate(total_families=models.Count('families'))

    males = person_data.filter(person__sex="Male", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__sex="Male").count()

    females = person_data.filter(person__sex="Female", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__sex="Female").count()

    total_population = males + females

    age_classifications = {
        'Infants': person_data.filter(person__age_class="Infant", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Infant").count(),
        'Toddlers': person_data.filter(person__age_class="Toddler", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Toddler").count(),
        'Childhood': person_data.filter(person__age_class="Childhood", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Childhood").count(),
        'Teenagers': person_data.filter(person__age_class="Teenage", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Teenage").count(),
        'Adults': person_data.filter(person__age_class="Adult", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Adult").count(),
        'Middle Aged Adults': person_data.filter(person__age_class="Middle Aged Adult", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Middle Aged Adult").count(),
        'Seniors': person_data.filter(person__age_class="Senior", person__barangay__icontains=selected_barangay).count() if selected_barangay else person_data.filter(person__age_class="Senior").count(),
    }

    context = {
        'total_households': households,
        'total_families': families['total_families'],
        'total_male': males,
        'total_female': females,
        'total_population': total_population,
        'age_classifications': json.dumps(age_classifications),  # Serialize as JSON
        'selected_barangay': selected_barangay,  # Pass the selected Barangay to the template
        'selected_year': selected_year,  # Pass the selected year to the template
        "year_range": year_range,
    }
    return render(request, 'dashboard/index.html', context)

