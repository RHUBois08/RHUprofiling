import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
import json
from django.utils.dateparse import parse_date
from datetime import datetime
from .models import Household, Person, PersonData, Family  # Add Family to the imports
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from uuid import UUID
from django.db.models import Q  # Import Q for complex queries
from django.urls import reverse  # Import reverse for URL generation
from django.core.paginator import Paginator  # Add this import
from django.contrib.auth.decorators import login_required

def validate_uuid(value):
    try:
        UUID(value, version=4)
    except ValueError:
        raise ValidationError(_('%(value)s is not a valid UUID.'), params={'value': value})

# @login_required
def index_view(request):
    search_query = request.GET.get('search', '').strip()  # Get the search query from the request
    households = Household.objects.prefetch_related('members', 'families__members').all()

    if search_query:
        search_parts = search_query.split()
        filters = Q()

        # Match first name
        if len(search_parts) > 0:
            filters |= Q(families__members__first_name__icontains=search_parts[0])

        # Match middle name
        if len(search_parts) > 1:
            filters |= Q(families__members__middle_name__icontains=search_parts[1])
        else:
            # If only one part is provided, also match it against the middle name
            filters |= Q(families__members__middle_name__icontains=search_parts[0])

        # Match last name
        if len(search_parts) > 2:
            filters |= Q(families__members__last_name__icontains=search_parts[2])
        else:
            # If only one part is provided, also match it against the last name
            filters |= Q(families__members__last_name__icontains=search_parts[0])

        # Add other filters
        filters |= (
            Q(families__members__suffix__icontains=search_query) |
            Q(house_number__icontains=search_query) |
            Q(barangay__icontains=search_query) |
            Q(purok__icontains=search_query)
        )

        households = households.filter(filters).distinct()

    data = []
    for household in households:
        head = household.members.filter(position='Head').first()
        families = household.families.prefetch_related('members').all()
        family_data = [
            {
                'family_name': family.family_name,
                'members': list(family.members.values('person_id', 'first_name', 'middle_name', 'last_name', 'sex', 'position'))
            }
            for family in families
        ]

        # Convert UUIDs to strings
        for family in family_data:
            for member in family['members']:
                member['person_id'] = str(member['person_id'])

        if head:
            data.append({
                'head_name': f"{head.first_name} {head.middle_name or ''} {head.last_name} {head.suffix if head.suffix != 'N/A' else ''}".strip(),
                'household_number': household.house_number,
                'sex': head.sex,
                'address': f"BRGY. {household.barangay}, PUROK-{household.purok}",
                'date_profiled': household.created,
                'families': family_data
            })

    # PAGINATION: Show 20 household heads per page
    page_number = request.GET.get('page', 1)
    paginator = Paginator(data, 20)
    page_obj = paginator.get_page(page_number)

    return render(request, 'records/index.html', {
        'households': page_obj.object_list,
        'search_query': search_query,
        'page_obj': page_obj,
        'paginator': paginator,
    })

def hhForm_view(request):
    return render(request, 'records/hh_form.html')

def profiling_view(request, household_number):
    household = get_object_or_404(Household, house_number=household_number)
    members = household.members.all()
    current_year = datetime.now().year
    
    # Get the selected year from the query parameters, default to the current year
    selected_year = int(request.GET.get('year', current_year))
    
    year_range = range(2025, current_year + 6)  # Generate the range of years

    # Fetch data for the selected year
    for member in members:
        member_data = PersonData.objects.filter(person=member, year=selected_year).first()
        if member_data:  # Include members with data for the selected year
            member.is_active = member_data.is_active  # Ensure is_active is passed to the template
            # Attach year-specific data to the member, but do NOT overwrite model fields like 'position'
            for key, value in member_data.data.items():
                if key == 'birthday' and value:
                    setattr(member, key, parse_date(value))
                elif key.endswith('_date') and value:
                    setattr(member, key, parse_date(value))
                elif key == 'health_condition' and isinstance(value, list):
                    setattr(member, key, value)
                elif key not in ['position']:  # <-- Do not overwrite position
                    setattr(member, key, value)
        else:
            # Set default values for members without data for the selected year
            member.is_active = True  # Default to inactive if no data
            member.prepared_by = None
            member.approved_by = None
            member.date_encoded = None
            # Add other fields as necessary

    return render(request, 'records/profiling.html', {
        'household': household,
        'members': members,  # Pass all members
        'year_range': year_range,  # Pass the range to the template
        'selected_year': selected_year,  # Pass the selected year to the template
        'current_date': datetime.now(),
    })

def save_household(request):
    if request.method == 'POST':
        house_number = request.POST.get('house_number')
        barangay = request.POST.get('barangay')
        purok = request.POST.get('purok')
        respondent = request.POST.get('respondent')
        no_of_family = int(request.POST.get('no_of_family', 1))

        # Validate required fields
        if not house_number or not barangay or not purok or not respondent:
            return render(request, 'records/hh_form.html', {'error': 'All household fields are required.'})

        # Check for duplicate household number
        if Household.objects.filter(house_number=house_number).exists():
            suffix = 'A'
            while Household.objects.filter(house_number=f"{house_number}-{suffix}").exists():
                suffix = chr(ord(suffix) + 1)
            if not request.POST.get('confirm_duplicate'):
                return render(request, 'records/hh_form.html', {
                    'error': f"Household number {house_number} already exists.",
                    'suggested_number': f"{house_number}-{suffix}",
                    'house_number': house_number,
                    'barangay': barangay,
                    'purok': purok,
                    'respondent': respondent,
                })
            house_number = f"{house_number}-{suffix}"

        # Create the Household
        household = Household.objects.create(
            house_number=house_number,
            barangay=barangay,
            purok=purok,
            respondent=respondent
        )

        # Create families and their members
        for family_index in range(1, no_of_family + 1):
            family = Family.objects.create(
                household=household,
                family_name=f"Household {family_index}"
            )

            last_names = request.POST.getlist(f'last_name_family_{family_index}[]')
            first_names = request.POST.getlist(f'first_name_family_{family_index}[]')
            middle_names = request.POST.getlist(f'middle_name_family_{family_index}[]')
            suffixes = request.POST.getlist(f'suffix_family_{family_index}[]')
            positions = request.POST.getlist(f'position_family_{family_index}[]')
            sexes = request.POST.getlist(f'sex_family_{family_index}[]')

            for last_name, first_name, middle_name, suffix, position, sex in zip(last_names, first_names, middle_names, suffixes, positions, sexes):
                if not last_name or not first_name or not position or not sex:
                    household.delete()  # Rollback household creation
                    return render(request, 'records/hh_form.html', {'error': 'All person fields are required.'})

                # Create the Person
                person = Person.objects.create(
                    family=family,
                    household=household,
                    barangay=barangay,
                    last_name=last_name,
                    first_name=first_name,
                    middle_name=middle_name,
                    suffix=suffix,
                    position=position,
                    sex=sex
                )

                # Save the person to PersonData for the current year
                PersonData.objects.create(
                    person=person,
                    year=datetime.now().year,
                    data={},  # Initialize with empty data
                    is_active=True  # Default to active
                )

        return render(request, 'records/hh_form.html', {'message': 'Data has been saved successfully.'})
    return redirect('records:index')

def delete_household(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON data
            household_number = data.get('household_number')
            if not household_number:
                return JsonResponse({'success': False, 'message': 'Household number is missing.'})
            
            household = Household.objects.get(house_number=household_number)
            household.delete()
            return JsonResponse({'success': True, 'message': 'Household deleted successfully.'})
        except Household.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Household not found.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

def save_profiling(request):
    if request.method == 'POST':
        try:
            person_id = request.POST.get('person_id')
            family_id = request.POST.get('family_id')  # Ensure family_id is retrieved
            year = request.POST.get('year') or datetime.now().year  # Default to current year if missing
            is_active = request.POST.get('status') == 'active'  # Get active/inactive status

            # Validate family_id as a UUID
            if not family_id:
                return JsonResponse({'success': False, 'message': 'Family ID is missing.'})
            try:
                validate_uuid(family_id)
            except ValidationError:
                return JsonResponse({'success': False, 'message': 'Invalid Family ID.'})

            # Fetch the family object
            try:
                family = Family.objects.prefetch_related('members').get(family_id=family_id)
            except Family.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Family not found.'})

            if person_id:  # Update existing member
                try:
                    person = Person.objects.get(person_id=person_id)
                except Person.DoesNotExist:
                    return JsonResponse({'success': False, 'message': 'Person not found.'})
            else:  # Add new member
                person = Person(family=family, household=family.household)  # Associate with family

            # Save the person details
            fields_to_save = [
                'last_name', 'first_name', 'middle_name', 'suffix', 'position', 'sex', 'birthday', 'age', 'age_class',
                'civil_status', 'education', 'contact_num', 'monthly_income', 'occupation', 'philhealth_member',
                'philhealth_number', 'nhts_member', 'four_ps_member', 'four_ps_number', 'health_condition',
                'other_health_condition', 'water_source', 'toilet_type', 'waste_segregation',
                'prepared_by', 'approved_by', 'date_encoded', 'expanded_newborn_screening', 'newborn_hearing_screening', 'newborn_immunization',
                'infant_immunization',
                'under5_immunization', 'under5_height', 'under5_weight', 'under5_muac', 'under5_weight_class', 'under5_height_class',
                'family_planning', 'fp_source', 'fp_payment_status',
                'twenty59_philpen_risk_assessment','vasectomy',
                'geriatric_screening', 'senior_philpen_risk_assessment', 'visual_acuity_test',
                'senior_flu_vaccine', 'senior_pneumonia_vaccine',
                'is_smoking', 'is_drinking', 'is_drug_user', 'high_risk_activities',
                'pwd_toggle',
                'buntis_toggle', 'pregnancy_order', 'birth_plan', 'prenatal_checkup', 'prenatal_location', 'prenatal_provider',
            ]

            for field in fields_to_save:
                value = request.POST.get(field, None)
                if field in ['birthday', 'last_mens', 'pregnant_gave_birth', 'postpartum_gave_birth', 'date_encoded']:
                    value = parse_date(value) if value else None
                    if value is None:
                        continue
                # Remove JSON/list handling for senior vaccine fields
                setattr(person, field, value)

            newborn_immunization = request.POST.getlist('newborn_immunization[]')  # Retrieve multiple values
            health_conditions = request.POST.getlist('health_condition[]')  # Retrieve multiple values
            other_health_conditions = request.POST.getlist('other_health_condition[]')  # Retrieve multiple values
            # Clean up: if the list is empty or contains only empty strings, treat as None
            if not other_health_conditions or all(not val.strip() for val in other_health_conditions):
                other_health_conditions = None
            infant_immunizations = request.POST.getlist('infant_immunization[]')  # Retrieve multiple values for infant_immunization
            five19_immunizations = request.POST.getlist('five19_immunization[]')  # Retrieve multiple values for five19_immunization
            under5_immunizations = request.POST.getlist('under5_immunization[]')  # Retrieve multiple values for under5_immunization
            is_pwd = request.POST.getlist('is_pwd[]')  # Retrieve multiple values for is_pwd
            sub_health_conditions = request.POST.getlist('sub_health_condition')  # Retrieve all sub_health_condition values
            other_fields = request.POST.dict()  # Get other fields as a dictionary

            # Save health_condition in the Person model
            person.newborn_immunization = newborn_immunization  # Save as a list
            person.health_condition = health_conditions  # Save as a list
            person.other_health_condition = other_health_conditions  # Save as a list or None
            person.infant_immunization = infant_immunizations  # Save in the Person model
            person.five19_immunization = five19_immunizations  # Save in the Person model
            person.under5_immunization = under5_immunizations  # Save in the Person model
            person.is_pwd = is_pwd  # Save in the Person model

            # Instead, handle as single values
            person.senior_flu_vaccine = request.POST.get('senior_flu_vaccine', None)
            person.senior_pneumonia_vaccine = request.POST.get('senior_pneumonia_vaccine', None)
            other_fields['senior_flu_vaccine'] = person.senior_flu_vaccine
            other_fields['senior_pneumonia_vaccine'] = person.senior_pneumonia_vaccine

            # Add these lines to retrieve and store the new screening fields
            cervical_cancer_screening = request.POST.getlist('cervical_cancer_screening[]')
            breast_cancer_screening = request.POST.getlist('breast_cancer_screening[]')

            person.cervical_cancer_screening = cervical_cancer_screening
            person.breast_cancer_screening = breast_cancer_screening

            # Build mapping for sub_health_condition
            sub_health_condition_map = {}
            for main_cond, field_name in [
                ("REPRODUCTIVE", "sub_health_condition_REPRODUCTIVE"),
                ("GASTROINTESTINAL", "sub_health_condition_GASTROINTESTINAL"),
                ("ENT/EYE/RESPIRATORY SYSTEM", "sub_health_condition_ENT_EYE_RESPIRATORY_SYSTEM"),
                ("GENITOURINARY", "sub_health_condition_GENITOURINARY"),
                ("BLOOD", "sub_health_condition_BLOOD"),
                ("ENDOCRINE AND GLANDULAR CANCER", "sub_health_condition_ENDOCRINE_AND_GLANDULAR_CANCER"),
                ("SKIN AND SOFT TISSUE", "sub_health_condition_SKIN_AND_SOFT_TISSUE"),
                ("NERVOUS SYSTEM AND BRAIN", "sub_health_condition_NERVOUS_SYSTEM_AND_BRAIN"),
                ("NEURODEVELOPMENTAL DISORDERS", "sub_health_condition_NEURODEVELOPMENTAL_DISORDERS"),
                ("SCHIZOPHRENIA SPECTRUM / PSYCHOTIC DISORDERS", "sub_health_condition_SCHIZOPHRENIA_SPECTRUM_PSYCHOTIC_DISORDERS"),
                ("MOOD (AFFECTIVE) DISORDERS", "sub_health_condition_MOOD_AFFECTIVE_DISORDERS"),
                ("ANXIETY DISORDER", "sub_health_condition_ANXIETY_DISORDER"),
                ("OBSESSIVE-COMPULSIVE AND RELATED DISORDERS", "sub_health_condition_OBSESSIVE_COMPULSIVE_AND_RELATED_DISORDERS"),
                ("TRAUMA AND STRESSOR-RELATED DISORDER", "sub_health_condition_TRAUMA_AND_STRESSOR_RELATED_DISORDER"),
                ("SUBSTANCE-RELATED AND ADDICTIVE DISORDER", "sub_health_condition_SUBSTANCE_RELATED_AND_ADDICTIVE_DISORDER"),
                ("NEUROCOGNITIVE DISORDERS", "sub_health_condition_NEUROCOGNITIVE_DISORDERS"),
                ("SLEEP-WAKE DISORDERS", "sub_health_condition_SLEEP_WAKE_DISORDERS"),
                ("CEREBROVASCULAR DISORDER", "sub_health_condition_CEREBROVASCULAR_DISORDER"),
                ("NEURODEGENERATIVE DISEASES", "sub_health_condition_NEURODEGENERATIVE_DISEASES"),
                ("DEMYELINATING DISEASES", "sub_health_condition_DEMYELINATING_DISEASES"),
                ("NEUROMUSCULAR DISORDER", "sub_health_condition_NEUROMUSCULAR_DISORDER"),
                ("EPILEPTIC AND SEIZURE DISORDERS", "sub_health_condition_EPILEPTIC_AND_SEIZURE_DISORDERS"),
                ("INFECTION OF THE NERVOUS SYSTEM", "sub_health_condition_INFECTION_OF_THE_NERVOUS_SYSTEM"),
                ("HEADACHE AND PAIN SYNDROME", "sub_health_condition_HEADACHE_AND_PAIN_SYNDROME"),
                ("DEVELOPMENTAL AND CONGENITAL DISORDERS", "sub_health_condition_DEVELOPMENTAL_AND_CONGENITAL_DISORDERS"),
                ("TRAUMATIC AND STRUCTURAL DISORDERS", "sub_health_condition_TRAUMATIC_AND_STRUCTURAL_DISORDERS"),
                ("OCULAR MOTILITY AND NEUROLOGICAL DISORDERS", "sub_health_condition_OCULAR_MOTILITY_AND_NEUROLOGICAL_DISORDERS"),
                ("EYE TRAUMA", "sub_health_condition_EYE_TRAUMA"),
                ("DISEASES OF THE EXTERNAL EAR", "sub_health_condition_DISEASES_OF_THE_EXTERNAL_EAR"),
                ("DISEASES OF THE MIDDLE EAR AND MASTOID", "sub_health_condition_DISEASES_OF_THE_MIDDLE_EAR_AND_MASTOID"),
                ("DISEASES OF THE INNER EAR", "sub_health_condition_DISEASES_OF_THE_INNER_EAR"),
                ("CONGENITAL AND DEVELOPMENTAL CONDITIONS", "sub_health_condition_CONGENITAL_AND_DEVELOPMENTAL_CONDITIONS"),
                ("INFLAMMATORY HEART DISEASE", "sub_health_condition_INFLAMMATORY_HEART_DISEASE"),
                ("CONGENITAL HEART DISEASE", "sub_health_condition_CONGENITAL_HEART_DISEASE"),
                ("VASCULAR DISEASES", "sub_health_condition_VASCULAR_DISEASES"),
                ("VENOUS AND LYMPHATIC DISORDERS", "sub_health_condition_VENOUS_AND_LYMPHATIC_DISORDERS"),
                ("UPPER RESPIRATORY TRACT INFECTION", "sub_health_condition_UPPER_RESPIRATORY_TRACT_INFECTION"),
                ("LOWER RESPIRATORY TRACT INFECTION", "sub_health_condition_LOWER_RESPIRATORY_TRACT_INFECTION"),
                ("CHRONIC RESPIRATORY DISEASES", "sub_health_condition_CHRONIC_RESPIRATORY_DISEASES"),
                ("PLEURAL DISEASES", "sub_health_condition_PLEURAL_DISEASES"),
                ("INTERSTITIAL AND OCCUPATIONAL LUNG DISEASES", "sub_health_condition_INTERSTITIAL_AND_OCCUPATIONAL_LUNG_DISEASES"),
                ("ORAL CAVITY, SALIVARY GLANDS AND JAW", "sub_health_condition_ORAL_CAVITY_SALIVARY_GLANDS_AND_JAW"),
                ("ESOPHAGEAL DISEASES" , "sub_health_condition_ESOPHAGEAL_DISEASES"),
                ("STOMACH AND DUODENAL DISEASES", "sub_health_condition_STOMACH_AND_DUODENAL_DISEASES"),
                ("INTESTINAL DISEASES", "sub_health_condition_INTESTINAL_DISEASES"),
                ("LIVER DISEASES", "sub_health_condition_LIVER_DISEASES"),
                ("GALLBLADDER AND BILIARY TRACT DISEASES", "sub_health_condition_GALLBLADDER_AND_BILIARY_TRACT_DISEASES"),
                ("PANCREATIC DISEASES", "sub_health_condition_PANCREATIC_DISEASES"),
                ("RECTAL AND ANAL DISORDERS", "sub_health_condition_RECTAL_AND_ANAL_DISORDERS"),
                ("HERNIAS", "sub_health_condition_HERNIAS"),
                ("MALABSORPTION AND NUTRITION-RELATED DISORDERS","sub_health_condition_MALABSORPTION_AND_NUTRITION_RELATED_DISORDERS"),
                ("INFECTIONS", "sub_health_condition_INFECTIONS"),
                ("INFLAMMATORY SKIN DISEASES", "sub_health_condition_INFLAMMATORY_SKIN_DISEASES"),
                ("URTICARIA AND ERYTHEMA", "sub_health_condition_URTICARIA_AND_ERYTHEMA"),
                ("BULLOUS DISORDERS", "sub_health_condition_BULLOUS_DISORDERS"),
                ("DISORDERS OF SKIN APPENDAGES", "sub_health_condition_DISORDERS_OF_SKIN_APPENDAGES"),
                ("PIGMENTARY DISORDERS", "sub_health_condition_PIGMENTARY_DISORDERS"),
                ("VASCULAR SKIN DISORDERS", "sub_health_condition_VASCULAR_SKIN_DISORDERS"),
                ("CONNECTIVE TISSUE AND AUTOIMMUNE SKIN DISEASES", "sub_health_condition_CONNECTIVE_TISSUE_AND_AUTOIMMUNE_SKIN_DISEASES"),
                ("INFLAMMATORY POLYARTHROPATHIES", "sub_health_condition_INFLAMMATORY_POLYARTHROPATHIES"),
                ("OSTEOARTHRITIS AND RELATED DISORDERS", "sub_health_condition_OSTEOARTHRITIS_AND_RELATED_DISORDERS"),
                ("SOFT TISSUE DISORDERS", "sub_health_condition_SOFT_TISSUE_DISORDERS"),
                ("DISORDERS OF THE SPINE", "sub_health_condition_DISORDERS_OF_THE_SPINE"),
                ("OSTEOPATHIES AND CHONDROPATHIES", "sub_health_condition_OSTEOPATHIES_AND_CHONDROPATHIES"),
                ("INFECTIOUS DISORDERS OF BONE AND JOINT", "sub_health_condition_INFECTIOUS_DISORDERS_OF_BONE_AND_JOINT"),
                ("DEFORMITIES AND ACQUIRED MUSCULOSKELETAL ABNORMALITIES", "sub_health_condition_DEFORMITIES_AND_ACQUIRED_MUSCULOSKELETAL_ABNORMALITIES"),
                ("TRAUMA-RELATED MUSCULOSKELETAL CONDITIONS", "sub_health_condition_TRAUMA_RELATED_MUSCULOSKELETAL_CONDITIONS"),
                ("KIDNEY DISORDERS", "sub_health_condition_KIDNEY_DISORDERS"),
                ("LOWER URINARY TRACT DISORDERS", "sub_health_condition_LOWER_URINARY_TRACT_DISORDERS"),
                ("DISEASES OF THE MALE GENITAL ORGANS", "sub_health_condition_DISEASES_OF_THE_MALE_GENITAL_ORGANS"),
                ("DISEASES OF THE FEMALE GENITAL ORGANS", "sub_health_condition_DISEASES_OF_THE_FEMALE_GENITAL_ORGANS"),
                ("MALIGNANCIES", "sub_health_condition_MALIGNANCIES"),
                ("PREGNANCY RELATED CONDITIONS", "sub_health_condition_PREGNANCY_RELATED_CONDITIONS"),
                ("LABOR AND DELIVERY", "sub_health_condition_LABOR_AND_DELIVERY"),
                ("PUERPERIUM", "sub_health_condition_PUERPERIUM"),
                ("FETAL AND MATERNAL FACTORS AFFECTING THE NEWBORN", "sub_health_condition_FETAL_AND_MATERNAL_FACTORS_AFFECTING_THE_NEWBORN"),
                ("DISORDERS RELATED TO GESTATION AND GROWTH", "sub_health_condition_DISORDERS_RELATED_TO_GESTATION_AND_GROWTH"),
                ("BIRTH ASPHYXIA AND RESPIRATORY CONDITIONS", "sub_health_condition_BIRTH_ASPHYXIA_AND_RESPIRATORY_CONDITIONS"),
                ("NEONATAL INFECTIONS", "sub_health_condition_NEONATAL_INFECTIONS"),
                ("HEMATOLOGIC AND METABOLIC DISORDERS", "sub_health_condition_HEMATOLOGIC_AND_METABOLIC_DISORDERS"),
                ("PERINATAL COMPLICATIONS AND INJURIES", "sub_health_condition_PERINATAL_COMPLICATIONS_AND_INJURIES"),
                ("CONGENITAL MALFORMATIONS OF THE NERVOUS SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_NERVOUS_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE CIRCULATORY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_CIRCULATORY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE RESPIRATORY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_RESPIRATORY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE EYE, EAR, FACE AND NECK", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_EYE_EAR_FACE_AND_NECK"),
                ("CONGENITAL MALFORMATIONS OF THE DIGESTIVE SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_DIGESTIVE_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE GENITOURINARY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_GENITOURINARY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS AND DEFORMITIES OF THE MUSCULOSKELETAL SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_AND_DEFORMITIES_OF_THE_MUSCULOSKELETAL_SYSTEM"),
                ("OTHER CONGENITAL MALFORMATIONS", "sub_health_condition_OTHER_CONGENITAL_MALFORMATIONS"),
            ]:
                sub_val = request.POST.get(field_name)
                if sub_val:
                    sub_health_condition_map[main_cond] = sub_val

            # If not using explicit names, fallback to zipped logic (for legacy forms)
            if not sub_health_condition_map and sub_health_conditions:
                # Try to pair with health_condition[] order
                health_conditions = request.POST.getlist('health_condition[]')
                for idx, main_cond in enumerate(health_conditions):
                    if idx < len(sub_health_conditions) and sub_health_conditions[idx]:
                        sub_health_condition_map[main_cond] = sub_health_conditions[idx]

            # Save sub_health_condition as mapping (JSON)
            person.sub_health_condition = sub_health_condition_map

            person.save()

            # Ensure health_condition is saved as a list in PersonData
            other_fields['newborn_immunization'] = newborn_immunization  # Save as a list
            other_fields['health_condition'] = health_conditions
            other_fields['other_health_condition'] = other_health_conditions  # Save as a list or None
            other_fields['infant_immunization'] = infant_immunizations  # Save as a list
            other_fields['under5_immunization'] = under5_immunizations  # Save as a list
            other_fields['five19_immunization'] = five19_immunizations  # Save as a list
            other_fields['is_pwd'] = is_pwd  # Save in the PersonData
            other_fields['sub_health_condition'] = sub_health_condition_map  # Save mapping in PersonData

            # Remove redundant key if it exists
            if 'other_health_condition[]' in other_fields:
                del other_fields['other_health_condition[]']

            # Only save the mapping in PersonData, not individual keys
            other_fields['sub_health_condition'] = sub_health_condition_map
            # Remove any sub_health_condition_* keys from other_fields
            for main_cond, field_name in [
                ("REPRODUCTIVE", "sub_health_condition_REPRODUCTIVE"),
                ("GASTROINTESTINAL", "sub_health_condition_GASTROINTESTINAL"),
                ("ENT/EYE/RESPIRATORY SYSTEM", "sub_health_condition_ENT_EYE_RESPIRATORY_SYSTEM"),
                ("GENITOURINARY", "sub_health_condition_GENITOURINARY"),
                ("BLOOD", "sub_health_condition_BLOOD"),
                ("ENDOCRINE AND GLANDULAR CANCER", "sub_health_condition_ENDOCRINE_AND_GLANDULAR_CANCER"),
                ("SKIN AND SOFT TISSUE", "sub_health_condition_SKIN_AND_SOFT_TISSUE"),
                ("NERVOUS SYSTEM AND BRAIN", "sub_health_condition_NERVOUS_SYSTEM_AND_BRAIN"),
                ("NEURODEVELOPMENTAL DISORDERS", "sub_health_condition_NEURODEVELOPMENTAL_DISORDERS"),
                ("SCHIZOPHRENIA SPECTRUM / PSYCHOTIC DISORDERS", "sub_health_condition_SCHIZOPHRENIA_SPECTRUM_PSYCHOTIC_DISORDERS"),
                ("MOOD (AFFECTIVE) DISORDERS", "sub_health_condition_MOOD_AFFECTIVE_DISORDERS"),
                ("ANXIETY DISORDER", "sub_health_condition_ANXIETY_DISORDER"),
                ("OBSESSIVE-COMPULSIVE AND RELATED DISORDERS", "sub_health_condition_OBSESSIVE_COMPULSIVE_AND_RELATED_DISORDERS"),
                ("TRAUMA AND STRESSOR-RELATED DISORDER", "sub_health_condition_TRAUMA_AND_STRESSOR_RELATED_DISORDER"),
                ("SUBSTANCE-RELATED AND ADDICTIVE DISORDER", "sub_health_condition_SUBSTANCE_RELATED_AND_ADDICTIVE_DISORDER"),
                ("NEUROCOGNITIVE DISORDERS", "sub_health_condition_NEUROCOGNITIVE_DISORDERS"),
                ("SLEEP-WAKE DISORDERS", "sub_health_condition_SLEEP_WAKE_DISORDERS"),
                ("CEREBROVASCULAR DISORDER", "sub_health_condition_CEREBROVASCULAR_DISORDER"),
                ("NEURODEGENERATIVE DISEASES", "sub_health_condition_NEURODEGENERATIVE_DISEASES"),
                ("DEMYELINATING DISEASES", "sub_health_condition_DEMYELINATING_DISEASES"),
                ("NEUROMUSCULAR DISORDER", "sub_health_condition_NEUROMUSCULAR_DISORDER"),
                ("EPILEPTIC AND SEIZURE DISORDERS", "sub_health_condition_EPILEPTIC_AND_SEIZURE_DISORDERS"),
                ("INFECTION OF THE NERVOUS SYSTEM", "sub_health_condition_INFECTION_OF_THE_NERVOUS_SYSTEM"),
                ("HEADACHE AND PAIN SYNDROME", "sub_health_condition_HEADACHE_AND_PAIN_SYNDROME"),
                ("DEVELOPMENTAL AND CONGENITAL DISORDERS", "sub_health_condition_DEVELOPMENTAL_AND_CONGENITAL_DISORDERS"),
                ("TRAUMATIC AND STRUCTURAL DISORDERS", "sub_health_condition_TRAUMATIC_AND_STRUCTURAL_DISORDERS"),
                ("OCULAR MOTILITY AND NEUROLOGICAL DISORDERS", "sub_health_condition_OCULAR_MOTILITY_AND_NEUROLOGICAL_DISORDERS"),
                ("EYE TRAUMA", "sub_health_condition_EYE_TRAUMA"),
                ("DISEASES OF THE EXTERNAL EAR", "sub_health_condition_DISEASES_OF_THE_EXTERNAL_EAR"),
                ("DISEASES OF THE MIDDLE EAR AND MASTOID", "sub_health_condition_DISEASES_OF_THE_MIDDLE_EAR_AND_MASTOID"),
                ("DISEASES OF THE INNER EAR", "sub_health_condition_DISEASES_OF_THE_INNER_EAR"),
                ("CONGENITAL AND DEVELOPMENTAL CONDITIONS", "sub_health_condition_CONGENITAL_AND_DEVELOPMENTAL_CONDITIONS"),
                ("INFLAMMATORY HEART DISEASE", "sub_health_condition_INFLAMMATORY_HEART_DISEASE"),
                ("CONGENITAL HEART DISEASE", "sub_health_condition_CONGENITAL_HEART_DISEASE"),
                ("VASCULAR DISEASES", "sub_health_condition_VASCULAR_DISEASES"),
                ("VENOUS AND LYMPHATIC DISORDERS", "sub_health_condition_VENOUS_AND_LYMPHATIC_DISORDERS"),
                ("UPPER RESPIRATORY TRACT INFECTION", "sub_health_condition_UPPER_RESPIRATORY_TRACT_INFECTION"),
                ("LOWER RESPIRATORY TRACT INFECTION", "sub_health_condition_LOWER_RESPIRATORY_TRACT_INFECTION"),
                ("CHRONIC RESPIRATORY DISEASES", "sub_health_condition_CHRONIC_RESPIRATORY_DISEASES"),
                ("PLEURAL DISEASES", "sub_health_condition_PLEURAL_DISEASES"),
                ("INTERSTITIAL AND OCCUPATIONAL LUNG DISEASES", "sub_health_condition_INTERSTITIAL_AND_OCCUPATIONAL_LUNG_DISEASES"),
                ("ORAL CAVITY, SALIVARY GLANDS AND JAW", "sub_health_condition_ORAL_CAVITY_SALIVARY_GLANDS_AND_JAW"),
                ("ESOPHAGEAL DISEASES" , "sub_health_condition_ESOPHAGEAL_DISEASES"),
                ("STOMACH AND DUODENAL DISEASES", "sub_health_condition_STOMACH_AND_DUODENAL_DISEASES"),
                ("INTESTINAL DISEASES", "sub_health_condition_INTESTINAL_DISEASES"),
                ("LIVER DISEASES", "sub_health_condition_LIVER_DISEASES"),
                ("GALLBLADDER AND BILIARY TRACT DISEASES", "sub_health_condition_GALLBLADDER_AND_BILIARY_TRACT_DISEASES"),
                ("PANCREATIC DISEASES", "sub_health_condition_PANCREATIC_DISEASES"),
                ("RECTAL AND ANAL DISORDERS", "sub_health_condition_RECTAL_AND_ANAL_DISORDERS"),
                ("HERNIAS", "sub_health_condition_HERNIAS"),
                ("MALABSORPTION AND NUTRITION-RELATED DISORDERS","sub_health_condition_MALABSORPTION_AND_NUTRITION_RELATED_DISORDERS"),
                ("INFECTIONS", "sub_health_condition_INFECTIONS"),
                ("INFLAMMATORY SKIN DISEASES", "sub_health_condition_INFLAMMATORY_SKIN_DISEASES"),
                ("URTICARIA AND ERYTHEMA", "sub_health_condition_URTICARIA_AND_ERYTHEMA"),
                ("BULLOUS DISORDERS", "sub_health_condition_BULLOUS_DISORDERS"),
                ("DISORDERS OF SKIN APPENDAGES", "sub_health_condition_DISORDERS_OF_SKIN_APPENDAGES"),
                ("PIGMENTARY DISORDERS", "sub_health_condition_PIGMENTARY_DISORDERS"),
                ("VASCULAR SKIN DISORDERS", "sub_health_condition_VASCULAR_SKIN_DISORDERS"),
                ("CONNECTIVE TISSUE AND AUTOIMMUNE SKIN DISEASES", "sub_health_condition_CONNECTIVE_TISSUE_AND_AUTOIMMUNE_SKIN_DISEASES"),
                ("INFLAMMATORY POLYARTHROPATHIES", "sub_health_condition_INFLAMMATORY_POLYARTHROPATHIES"),
                ("OSTEOARTHRITIS AND RELATED DISORDERS", "sub_health_condition_OSTEOARTHRITIS_AND_RELATED_DISORDERS"),
                ("SOFT TISSUE DISORDERS", "sub_health_condition_SOFT_TISSUE_DISORDERS"),
                ("DISORDERS OF THE SPINE", "sub_health_condition_DISORDERS_OF_THE_SPINE"),
                ("OSTEOPATHIES AND CHONDROPATHIES", "sub_health_condition_OSTEOPATHIES_AND_CHONDROPATHIES"),
                ("INFECTIOUS DISORDERS OF BONE AND JOINT", "sub_health_condition_INFECTIOUS_DISORDERS_OF_BONE_AND_JOINT"),
                ("DEFORMITIES AND ACQUIRED MUSCULOSKELETAL ABNORMALITIES", "sub_health_condition_DEFORMITIES_AND_ACQUIRED_MUSCULOSKELETAL_ABNORMALITIES"),
                ("TRAUMA-RELATED MUSCULOSKELETAL CONDITIONS", "sub_health_condition_TRAUMA_RELATED_MUSCULOSKELETAL_CONDITIONS"),
                ("KIDNEY DISORDERS", "sub_health_condition_KIDNEY_DISORDERS"),
                ("LOWER URINARY TRACT DISORDERS", "sub_health_condition_LOWER_URINARY_TRACT_DISORDERS"),
                ("DISEASES OF THE MALE GENITAL ORGANS", "sub_health_condition_DISEASES_OF_THE_MALE_GENITAL_ORGANS"),
                ("DISEASES OF THE FEMALE GENITAL ORGANS", "sub_health_condition_DISEASES_OF_THE_FEMALE_GENITAL_ORGANS"),
                ("MALIGNANCIES", "sub_health_condition_MALIGNANCIES"),
                ("PREGNANCY RELATED CONDITIONS", "sub_health_condition_PREGNANCY_RELATED_CONDITIONS"),
                ("LABOR AND DELIVERY", "sub_health_condition_LABOR_AND_DELIVERY"),
                ("PUERPERIUM", "sub_health_condition_PUERPERIUM"),
                ("FETAL AND MATERNAL FACTORS AFFECTING THE NEWBORN", "sub_health_condition_FETAL_AND_MATERNAL_FACTORS_AFFECTING_THE_NEWBORN"),
                ("DISORDERS RELATED TO GESTATION AND GROWTH", "sub_health_condition_DISORDERS_RELATED_TO_GESTATION_AND_GROWTH"),
                ("BIRTH ASPHYXIA AND RESPIRATORY CONDITIONS", "sub_health_condition_BIRTH_ASPHYXIA_AND_RESPIRATORY_CONDITIONS"),
                ("NEONATAL INFECTIONS", "sub_health_condition_NEONATAL_INFECTIONS"),
                ("HEMATOLOGIC AND METABOLIC DISORDERS", "sub_health_condition_HEMATOLOGIC_AND_METABOLIC_DISORDERS"),
                ("PERINATAL COMPLICATIONS AND INJURIES", "sub_health_condition_PERINATAL_COMPLICATIONS_AND_INJURIES"),
                ("CONGENITAL MALFORMATIONS OF THE NERVOUS SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_NERVOUS_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE CIRCULATORY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_CIRCULATORY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE RESPIRATORY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_RESPIRATORY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE EYE, EAR, FACE AND NECK", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_EYE_EAR_FACE_AND_NECK"),
                ("CONGENITAL MALFORMATIONS OF THE DIGESTIVE SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_DIGESTIVE_SYSTEM"),
                ("CONGENITAL MALFORMATIONS OF THE GENITOURINARY SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_OF_THE_GENITOURINARY_SYSTEM"),
                ("CONGENITAL MALFORMATIONS AND DEFORMITIES OF THE MUSCULOSKELETAL SYSTEM", "sub_health_condition_CONGENITAL_MALFORMATIONS_AND_DEFORMITIES_OF_THE_MUSCULOSKELETAL_SYSTEM"),
                ("OTHER CONGENITAL MALFORMATIONS", "sub_health_condition_OTHER_CONGENITAL_MALFORMATIONS"),
            ]:
                if field_name in other_fields:
                    del other_fields[field_name]

            # Save year-specific data in PersonData
            person_data, created = PersonData.objects.get_or_create(
                person=person,
                year=year,  # Ensure year is passed here
                defaults={'data': {}, 'is_active': is_active}
            )
            if not created:
                person_data.data = other_fields  # Save all fields, including health_condition
                person_data.is_active = is_active  # Update active/inactive status

            # Store the new screening fields in PersonData's data dictionary
            person_data.data['cervical_cancer_screening'] = cervical_cancer_screening
            person_data.data['breast_cancer_screening'] = breast_cancer_screening

            person_data.save()

            # Prepare the updated family data for the response
            updated_family = {
                'family_id': str(family.family_id),
                'family_name': family.family_name,
                'members': list(family.members.values('person_id', 'first_name', 'middle_name', 'last_name', 'sex', 'position'))
            }

            return JsonResponse({'success': True, 'message': 'Data saved successfully.', 'family': updated_family})

        except Exception as e:
            # Log the error for debugging
            print(f"Error in save_profiling: {e}")
            return JsonResponse({'success': False, 'message': 'An unexpected error occurred.'}, status=500)

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

@csrf_exempt
def remove_member(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON data
            person_id = data.get('person_id')
            if not person_id:
                return JsonResponse({'success': False, 'message': 'Person ID is missing.'})
            
            # Validate the UUID
            validate_uuid(person_id)

            member = Person.objects.get(person_id=person_id)
            member.delete()
            return JsonResponse({'success': True, 'message': 'Member removed successfully.'})
        except ValidationError:
            return JsonResponse({'success': False, 'message': 'Invalid UUID provided.'})
        except Person.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Member not found.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

from django.http import JsonResponse

def get_household_data(request, household_number):
    try:
        household = Household.objects.prefetch_related('families__members').get(house_number=household_number)
        head = household.members.filter(position='Head').first()
        families = household.families.prefetch_related('members').all()

        family_data = [
            {
                'family_id': str(family.family_id),  # Include family_id and convert UUID to string
                'family_name': family.family_name,
                'members': list(family.members.values('person_id', 'first_name', 'middle_name', 'last_name', 'suffix', 'sex', 'position'))
            }
            for family in families
        ]

        # Convert UUIDs for members
        for family in family_data:
            for member in family['members']:
                member['person_id'] = str(member['person_id'])

        response_data = {
            'head_name': f"{head.first_name} {head.middle_name or ''} {head.last_name} {head.suffix if head.suffix != 'N/A' else ''}".strip() if head else "",
            'household_number': household.house_number,
            'families': family_data,
        }
        return JsonResponse(response_data, safe=False)
    except Household.DoesNotExist:
        return JsonResponse({'error': 'Household not found'}, status=404)

@csrf_exempt
def add_family(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON data
            household_number = data.get('household_number')
            if not household_number:
                return JsonResponse({'success': False, 'message': 'Household number is missing.'})

            # Fetch the household
            household = Household.objects.get(house_number=household_number)

            # Generate a new family name
            family_count = household.families.count() + 1
            family_name = f"Household {family_count}"

            # Create the new family
            family = Family.objects.create(household=household, family_name=family_name)

            return JsonResponse({
                'success': True,
                'message': 'Household added successfully.',
                'family_id': str(family.family_id),
                'family_name': family_name
            })
        except Household.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Household not found.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})

@csrf_exempt
def remove_family(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Parse JSON data
            family_id = data.get('family_id')
            if not family_id:
                return JsonResponse({'success': False, 'message': 'Family ID is missing.'})

            # Validate the UUID
            validate_uuid(family_id)

            # Fetch the family, delete all its members, and then delete the family
            family = Family.objects.get(family_id=family_id)
            family.members.all().delete()
            family.delete()

            return JsonResponse({'success': True, 'message': 'Household and its members have been removed.'})
        except ValidationError:
            return JsonResponse({'success': False, 'message': 'Invalid Family ID provided.'})
        except Family.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Family not found.'})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'Invalid JSON data.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'})
    return JsonResponse({'success': False, 'message': 'Invalid request method.'})
