from django.shortcuts import render
from django.db import models
from records.models import Household, Person, Family, PersonData
from datetime import datetime, date
from django.contrib.auth.decorators import login_required

def get_report_context(request):
    selected_barangay = request.GET.get('barangay', '')  # Get the selected Barangay from the request
    current_year = datetime.now().year
    
    # Get the selected year from the query parameters, default to the current year
    selected_year = int(request.GET.get('year', current_year))
    
    year_range = range(2025, current_year + 6)  # Generate the range of years
    
    # Filter households, families, and persons based on the selected Barangay and year
    households = Household.objects.filter(barangay__icontains=selected_barangay) if selected_barangay else Household.objects.all()
    families = Family.objects.filter(household__barangay__icontains=selected_barangay) if selected_barangay else Family.objects.all()
    persons = Person.objects.filter(barangay__icontains=selected_barangay) if selected_barangay else Person.objects.all()

    # Filter PersonData for the selected year
    person_data = PersonData.objects.filter(year=selected_year, person__in=persons)

    total_households = households.count()
    total_families = families.count()

    age_classifications = {
        "Infants_Male": person_data.filter(data__age_class="Infant", person__sex="Male").count(),
        "Infants_Female": person_data.filter(data__age_class="Infant", person__sex="Female").count(),
        "Toddler_Male": person_data.filter(data__age_class="Toddler", person__sex="Male").count(),
        "Toddler_Female": person_data.filter(data__age_class="Toddler", person__sex="Female").count(),
        "Childhood_Male": person_data.filter(data__age_class="Childhood", person__sex="Male").count(),
        "Childhood_Female": person_data.filter(data__age_class="Childhood", person__sex="Female").count(),
        "Teenage_Male": person_data.filter(data__age_class="Teenage", person__sex="Male").count(),
        "Teenage_Female": person_data.filter(data__age_class="Teenage", person__sex="Female").count(),
        "Adults_Male": person_data.filter(data__age_class="Adult", person__sex="Male").count(),
        "Adults_Female": person_data.filter(data__age_class="Adult", person__sex="Female").count(),
        "MiddleAged_Male": person_data.filter(data__age_class="Middle Aged Adult", person__sex="Male").count(),
        "MiddleAged_Female": person_data.filter(data__age_class="Middle Aged Adult", person__sex="Female").count(),
        "Seniors_Male": person_data.filter(data__age_class="Senior", person__sex="Male").count(),
        "Seniors_Female": person_data.filter(data__age_class="Senior", person__sex="Female").count(),
    }

    today = date.today()

    def calculate_age(birthday_str):
        try:
            birthday = datetime.strptime(birthday_str, "%Y-%m-%d").date()
            return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))
        except (ValueError, TypeError):
            return None

    wra_count = person_data.filter(
        person__sex="Female",
        person__birthday__isnull=False
    ).annotate(
        calculated_age=models.ExpressionWrapper(
            today.year - models.F("person__birthday__year") - models.Case(
                models.When(
                    models.Q(person__birthday__month__gt=today.month) |
                    models.Q(person__birthday__month=today.month, person__birthday__day__gt=today.day),
                    then=1
                ),
                default=0,
                output_field=models.IntegerField()
            ),
            output_field=models.IntegerField()
        )
    ).filter(calculated_age__gte=14, calculated_age__lte=49).count()

    family_planning_count = person_data.filter(
        models.Q(data__birth_plan__isnull=False) & ~models.Q(data__birth_plan="")
    ).count()
    
    pregnant_count = person_data.filter(data__buntis_toggle__iexact="YES").count()

    water_sources = {
        "Level 1": person_data.filter(
            models.Q(data__water_source="Level 1") & ~models.Q(data__water_source="")
        ).count(),
        "Level 2": person_data.filter(
            models.Q(data__water_source="Level 2") & ~models.Q(data__water_source="")
        ).count(),
        "Level 3": person_data.filter(
            models.Q(data__water_source="Level 3") & ~models.Q(data__water_source="")
        ).count(),
    }
    toilet_types = {
        "Shared": person_data.filter(
            models.Q(data__toilet_type="Shared") & ~models.Q(data__toilet_type="")
        ).count(),
        "Owned": person_data.filter(
            models.Q(data__toilet_type="Owned") & ~models.Q(data__toilet_type="")
        ).count(),
        "None": person_data.filter(
            models.Q(data__toilet_type="None") & ~models.Q(data__toilet_type="")
        ).count(),
    }

    def fetch_health_conditions(person_data):
        """
        Fetch and count health conditions for males and females from the records_persondata table.
        """
        health_conditions = {}

        # List of health condition codes and their descriptions
        condition_categories = [
            "A00-B99", "C00-D49", "D50-D89", "E00-E89", "F01-F99",
            "G00-G99", "H00-H59", "H60-H95", "I00-I99", "J00-J99",
            "K00-K95", "L00-L99", "M00-M99", "N00-N99", "O00-O9A",
            "P00-P96", "Q00-Q99", "R00-R99", "S00-T88", "U00-U85",
            "V00-Y99", "Z00-Z99",
        ]

        # Loop through each condition category and count occurrences for males and females
        for code in condition_categories:
            health_conditions[code] = {
                "Male": person_data.filter(data__health_condition__icontains=code, person__sex="Male").count(),
                "Female": person_data.filter(data__health_condition__icontains=code, person__sex="Female").count(),
            }

        return health_conditions

    health_conditions = fetch_health_conditions(person_data)
    

    sick_persons = set()

    for person_data_item in person_data:
        health_condition = person_data_item.data.get('health_condition', [])
        other_health_condition = person_data_item.data.get('other_health_condition', [])

        # Normalize health_condition to a list
        if isinstance(health_condition, str):
            health_condition = [s.strip() for s in health_condition.split(',')]
        
        # Normalize other_health_condition to a list
        if isinstance(other_health_condition, str):
            other_health_condition = [s.strip() for s in other_health_condition.split(',')]
        
        if other_health_condition is None:
            other_health_condition = []

        # Check if health_condition contains valid conditions
        valid_health_condition = any(
            cond and cond.lower() != "walang sakit" for cond in health_condition if isinstance(cond, str)
        )

        # Check if other_health_condition contains valid conditions
        valid_other_health_condition = any(
            cond and cond.lower() != "none" for cond in other_health_condition if isinstance(cond, str)
        )

        if valid_health_condition or valid_other_health_condition:
            sick_persons.add(person_data_item.person_id)

    may_sakit_count = len(sick_persons)

    pwd_count = person_data.filter(data__pwd_toggle__iexact="YES").count()

    def calculate_sickness_counts(person_data, diseases_data):
        """
        Calculate sickness counts for each disease based on diseasesData.
        """
        sickness_counts = []
        for code, diseases in diseases_data.items():
            for disease in diseases:
                male_count = person_data.filter(data__health_condition__icontains=disease, person__sex="Male").count()
                female_count = person_data.filter(data__health_condition__icontains=disease, person__sex="Female").count()
                sickness_counts.append({
                    "code": code,
                    "disease": disease,
                    "male_count": male_count,
                    "female_count": female_count,
                    "total_count": male_count + female_count,
                })
        return sickness_counts

    # Example diseasesData (replace with actual data source)
    diseases_data = {
        "A00-B99": ["TUBERCULOSIS", "DENGUE", "MALARIA", "HIV/AIDS", "MEASLES", "RABIES", "TETANUS", "CHOLERA", "CHIKUNGUNYA", "ZIKA VIRUS", "COVID-19"],
            "C00-D49": ["REPRODUCTIVE", "GASTROINTESTINAL", "ENT/EYE/RESPIRATORY SYSTEM", "GENITOURINARY", "BLOOD", "ENDOCRINE AND GLANDULAR CANCER", "SKIN AND SOFT TISSUE", "NERVOUS SYSTEM AND BRAIN"],
            "D50-D89": ["ANEMIA", "LEUKEMIA", "LYMPHOPROLIFERATIVE AND OTHER DISORDERS", "PLATELET DISORDER", "CLOTTING FACTOR DISORDER", "BONE MARROW FAILURE SYNDROME"],
            "E00-E89": ["DIABETES MELLITUS", "HYPOTHYROIDISM", "HYPERTHYROIDISM", "OBESITY", "GOITER", "CUSHING'S SYNDROME"],
            "F01-F99": ["NEURODEVELOPMENTAL DISORDERS", "SCHIZOPHRENIA SPECTRUM / PSYCHOTIC DISORDERS", "MOOD (AFFECTIVE) DISORDERS", "ANXIETY DISORDER", "OBSESSIVE-COMPULSIVE AND RELATED DISORDERS", "TRAUMA AND STRESSOR-RELATED DISORDER", "SUBSTANCE-RELATED AND ADDICTIVE DISORDER", "NEUROCOGNITIVE DISORDERS", "SLEEP-WAKE DISORDERS"],
            "G00-G99": ["CEREBROVASCULAR DISORDER", "NEURODEGENERATIVE DISEASES", "DEMYELINATING DISEASES", "NEUROMUSCULAR DISORDER", "EPILEPTIC AND SEIZURE DISORDERS", "INFECTION OF THE NERVOUS SYSTEM", "HEADACHE AND PAIN SYNDROME", "DEVELOPMENTAL AND CONGENITAL DISORDERS", "TRAUMATIC AND STRUCTURAL DISORDERS"],
            "H00-H59": ["REFRACTIVE ERRORS", "LENS DISORDERS (CATARACT/ LENS DISLOCATION)", "GLAUCOMA", "RETINAL DISORDERS", "OCULAR MOTILITY AND NEUROLOGICAL DISORDERS", "EYE TRAUMA"],
            "H60-H95": ["DISEASES OF THE EXTERNAL EAR", "DISEASES OF THE MIDDLE EAR AND MASTOID", "DISEASES OF THE INNER EAR", "HEARING LOSS", "TINNITUS AND RELATED DISORDERS", "CONGENITAL AND DEVELOPMENTAL CONDITIONS"],
            "I00-I99": ["HYPERTENSIVE DISORDER", "ISCHEMIC HEART DISEASE", "HEART FAILURE", "CARDIOMYOPATHIES", "CARDIAC ARRHYTHMIAS", "INFLAMMATORY HEART DISEASE", "VALVULAR HEART DISEASE", "CONGENITAL HEART DISEASE", "VASCULAR DISEASES", "VENOUS AND LYMPHATIC DISORDERS"],
            "J00-J99": ["UPPER RESPIRATORY TRACT INFECTION", "LOWER RESPIRATORY TRACT INFECTION", "CHRONIC RESPIRATORY DISEASES", "PLEURAL DISEASES", "INTERSTITIAL AND OCCUPATIONAL LUNG DISEASES"],
            "K00-K95": ["ORAL CAVITY, SALIVARY GLANDS AND JAW", "ESOPHAGEAL DISEASES", "STOMACH AND DUODENAL DISEASES", "INTESTINAL DISEASES", "LIVER DISEASES", "GALLBLADDER AND BILIARY TRACT DISEASES", "PANCREATIC DISEASES", "RECTAL AND ANAL DISORDERS", "HERNIAS", "MALABSORPTION AND NUTRITION-RELATED DISORDERS"],
            "L00-L99": ["INFECTIONS", "INFLAMMATORY SKIN DISEASES", "URTICARIA AND ERYTHEMA", "BULLOUS DISORDERS", "DISORDERS OF SKIN APPENDAGES", "PIGMENTARY DISORDERS", "VASCULAR SKIN DISORDERS", "CONNECTIVE TISSUE AND AUTOIMMUNE SKIN DISEASES"],
            "M00-M99": ["INFLAMMATORY POLYARTHROPATHIES", "OSTEOARTHRITIS AND RELATED DISORDERS", "SOFT TISSUE DISORDERS", "DISORDERS OF THE SPINE", "OSTEOPATHIES AND CHONDROPATHIES", "INFECTIOUS DISORDERS OF BONE AND JOINT", "DEFORMITIES AND ACQUIRED MUSCULOSKELETAL ABNORMALITIES", "TRAUMA-RELATED MUSCULOSKELETAL CONDITIONS"],
            "N00-N99": ["KIDNEY DISORDERS", "LOWER URINARY TRACT DISORDERS", "DISEASES OF THE MALE GENITAL ORGANS", "DISEASES OF THE FEMALE GENITAL ORGANS", "MALIGNANCIES"],
            "O00-O99": ["PREGNANCY RELATED CONDITIONS", "LABOR AND DELIVERY", "PUERPERIUM"],
            "P00-P96": ["FETAL AND MATERNAL FACTORS AFFECTING THE NEWBORN", "DISORDERS RELATED TO GESTATION AND GROWTH", "BIRTH ASPHYXIA AND RESPIRATORY CONDITIONS", "NEONATAL INFECTIONS", "HEMATOLOGIC AND METABOLIC DISORDERS", "PERINATAL COMPLICATIONS AND INJURIES"],
            "Q00-Q99": ["CONGENITAL MALFORMATIONS OF THE NERVOUS SYSTEM", "CONGENITAL MALFORMATIONS OF THE CIRCULATORY SYSTEM", "CONGENITAL MALFORMATIONS OF THE RESPIRATORY SYSTEM", "CONGENITAL MALFORMATIONS OF THE EYE, EAR, FACE AND NECK", "CONGENITAL MALFORMATIONS OF THE DIGESTIVE SYSTEM", "CONGENITAL MALFORMATIONS OF THE GENITOURINARY SYSTEM", "CONGENITAL MALFORMATIONS AND DEFORMITIES OF THE MUSCULOSKELETAL SYSTEM", "OTHER CONGENITAL MALFORMATIONS"],
        # ...add other disease mappings...
    }

    # Calculate sickness counts
    sickness_counts = calculate_sickness_counts(person_data, diseases_data)

    # Fetch other health conditions and their counts
    other_health_condition = {}
    all_other_health_conditions = []

    for person_data_item in person_data:
        if person_data_item.data and person_data_item.data.get('other_health_condition'):
            other_health_conditions = person_data_item.data['other_health_condition']
            if isinstance(other_health_conditions, str):
                other_health_conditions = [s.strip() for s in other_health_conditions.split(',')]
            
            all_other_health_conditions.extend(other_health_conditions)

    unique_other_health_conditions = list(set(all_other_health_conditions))

    for condition in unique_other_health_conditions:
        if not condition or condition.lower() == "none":  # Skip empty conditions and "None"
            continue
        male_count = person_data.filter(data__other_health_condition__icontains=condition, person__sex="Male").count()
        female_count = person_data.filter(data__other_health_condition__icontains=condition, person__sex="Female").count()
        other_health_condition[condition] = {
            'male_count': male_count,
            'female_count': female_count,
            'total_count': male_count + female_count,
        }

    # Sort other_health_condition alphabetically by condition
    other_health_condition = dict(sorted(other_health_condition.items()))

    sickness_code_descriptions = {
        "A00-B99": "Certain infectious and parasitic diseases",
        "C00-D49": "Neoplasms",
        "D50-D89": "Diseases of the blood and blood-forming organs and certain disorders",
        "E00-E89": "Endocrine, nutritional and metabolic diseases",
        "F01-F99": "Mental, Behavioral and Neurodevelopmental disorders",
        "G00-G99": "Diseases of the nervous system",
        "H00-H59": "Diseases of the eye and adnexa",
        "H60-H95": "Diseases of the ear and mastoid process",
        "I00-I99": "Diseases of the circulatory system",
        "J00-J99": "Diseases of the respiratory system",
        "K00-K95": "Diseases of the digestive system",
        "L00-L99": "Diseases of the skin and subcutaneous tissue",
        "M00-M99": "Diseases of the musculoskeletal system and connective tissue",
        "N00-N99": "Diseases of the genitourinary system",
        "O00-O9A": "Pregnancy, childbirth and the puerperium",
        "P00-P96": "Certain conditions originating in the perinatal period",
        "Q00-Q99": "Congenital malformations, deformations and chromosomal abnormalities",
    }

    # --- PWD breakdown by is_pwd field ---
    # Collect all unique PWD types from is_pwd in the data JSON, only for those with pwd_toggle YES
    pwd_types = set()
    for pd in person_data.filter(data__pwd_toggle__iexact="YES"):
        is_pwd_val = pd.data.get("is_pwd", [])
        if isinstance(is_pwd_val, str):
            is_pwd_val = [s.strip() for s in is_pwd_val.split(",") if s.strip()]
        for typ in is_pwd_val:
            if typ and typ.lower() != "none":
                pwd_types.add(typ)
    pwd_types = sorted(pwd_types)

    pwd_table = []
    for typ in pwd_types:
        male_count = person_data.filter(data__pwd_toggle__iexact="YES", data__is_pwd__icontains=typ, person__sex="Male").count()
        female_count = person_data.filter(data__pwd_toggle__iexact="YES", data__is_pwd__icontains=typ, person__sex="Female").count()
        pwd_table.append({
            "type": typ,
            "male_count": male_count,
            "female_count": female_count,
            "total_count": male_count + female_count,
        })

    context = {
        "total_households": total_households,
        "total_families": total_families,
        "age_classifications": age_classifications,
        "wra_count": wra_count,
        "family_planning_count": family_planning_count,
        "pregnant_count": pregnant_count,
        "water_sources": water_sources,
        "toilet_types": toilet_types,
        "level1_count": water_sources["Level 1"],
        "shared_toilet_count": toilet_types["Shared"],
        "level2_count": water_sources["Level 2"],
        "owned_toilet_count": toilet_types["Owned"],
        "level3_count": water_sources["Level 3"],
        "none_toilet_count": toilet_types["None"],
        "health_conditions": health_conditions,
        "may_sakit_count": may_sakit_count,
        "selected_barangay": selected_barangay,  # Pass the selected Barangay to the template
        "selected_year": selected_year,  # Pass the selected year to the template
        "year_range": year_range,  # Pass the year range to the template
        "sickness_counts": sickness_counts,  # Add sickness counts to context
        "other_health_condition": other_health_condition,
        "sickness_code_descriptions": sickness_code_descriptions,
        "pwd_count": pwd_count,
        "pwd_table": pwd_table,
    }

    return context

# @login_required
def index_view(request):
    context = get_report_context(request)
    return render(request, "reports/index.html", context)

def print_report_view(request):
    context = get_report_context(request)
    return render(request, "reports/print_report.html", context)
