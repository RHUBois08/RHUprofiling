from django.db import models
import uuid
from datetime import datetime
from django.contrib.postgres.fields import JSONField  # Add this import if using Postgres

class Household(models.Model):
    house_number = models.CharField(max_length=50, primary_key=True)  # Set house_number as PK
    barangay = models.CharField(max_length=100)
    purok = models.CharField(max_length=100)
    respondent = models.CharField(max_length=100)
    created = models.DateTimeField(auto_now=True)
    year = models.IntegerField(default=datetime.now().year)  # Add a year field

    def __str__(self):
        return self.house_number

class Family(models.Model):
    family_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name='families'
    )
    family_name = models.CharField(max_length=100)  # Optional name for the family
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Family {self.family_name} in Household {self.household.house_number}"

class Person(models.Model):
    person_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, primary_key=True)
    household = models.ForeignKey(
        Household, 
        on_delete=models.CASCADE, 
        related_name='members'
    )
    family = models.ForeignKey(
        Family,
        on_delete=models.CASCADE,
        related_name='members',
        null=True,  # Allow null for backward compatibility
        blank=True
    )
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, null=True)
    suffix = models.CharField(max_length=10, blank=True, null=True)
    position = models.CharField(max_length=50)
    sex = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')], default='Male')
    birthday = models.DateField(blank=True, null=True)
    age = models.CharField(max_length=50, blank=True, null=True)
    age_class = models.CharField(max_length=50, blank=True, null=True)
    civil_status = models.CharField(max_length=50, blank=True, null=True)
    education = models.CharField(max_length=100, blank=True, null=True)
    contact_num = models.CharField(max_length=15, blank=True, null=True)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    philhealth_member = models.CharField(max_length=10, blank=True, null=True)
    philhealth_number = models.CharField(max_length=50, blank=True, null=True)
    nhts_member = models.CharField(max_length=10, blank=True, null=True)
    four_ps_member = models.CharField(max_length=10, blank=True, null=True)
    four_ps_number = models.CharField(max_length=50, blank=True, null=True)
    health_condition = models.TextField(blank=True, null=True)
    other_health_condition = models.TextField(blank=True, null=True)
    # Change sub_health_condition to JSONField for mapping
    sub_health_condition = models.JSONField(blank=True, null=True)  # Store as mapping, e.g., {"REPRODUCTIVE": "Breast Cancer"}
    water_source = models.CharField(max_length=50, blank=True, null=True)
    toilet_type = models.CharField(max_length=50, blank=True, null=True)
    waste_segregation = models.CharField(max_length=10, blank=True, null=True)
    prepared_by = models.CharField(max_length=100, blank=True, null=True)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    date_encoded = models.DateTimeField(blank=True, null=True)
    
    # 0 days to 28 days
    expanded_newborn_screening = models.CharField(max_length=50, blank=True, null=True)
    newborn_immunization = models.TextField(blank=True, null=True)
    newborn_hearing_screening = models.CharField(max_length=50, blank=True, null=True)
    
    # 29 days to 59 months
    infant_immunization = models.TextField(blank=True, null=True)
    
    # under 5 years old
    under5_immunization = models.TextField(blank=True, null=True)
    under5_height = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    under5_weight = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    under5_muac = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    under5_weight_class = models.CharField(max_length=50, blank=True, null=True)
    under5_height_class = models.CharField(max_length=50, blank=True, null=True)
    
    # 5 - 19 years old
    five19_immunization = models.TextField(blank=True, null=True)
    
    # 14 to 49 years old Women 
    family_planning = models.CharField(max_length=50, blank=True, null=True)
    fp_source = models.CharField(max_length=100, blank=True, null=True)
    fp_payment_status = models.CharField(max_length=50, blank=True, null=True)
    
    # 30-69 years old
    cervical_cancer_screening = models.TextField(blank=True, null=True)  # Store as text field
    breast_cancer_screening = models.TextField(blank=True, null=True)  # Store as text field
    
    # 20-59 years old
    twenty59_philpen_risk_assessment = models.CharField(max_length=50, blank=True, null=True)
    vasectomy = models.CharField(max_length=10, blank=True, null=True)
    
    
    
    # 60 years old and above
    senior_flu_vaccine = models.CharField(max_length=50, blank=True, null=True)  # Store a single date as string
    senior_pneumonia_vaccine = models.CharField(max_length=50, blank=True, null=True)  # Store a single date as string
    geriatric_screening = models.CharField(max_length=50, blank=True, null=True)  # Store a single date as string
    senior_philpen_risk_assessment = models.CharField(max_length=50, blank=True, null=True)  # Store a single date as string
    visual_acuity_test = models.CharField(max_length=50, blank=True, null=True)  # Store a single date as string
    
    # 12 years old and above (Male and Female)
    is_smoking = models.CharField(max_length=10, blank=True, null=True)
    is_drinking = models.CharField(max_length=10, blank=True, null=True)
    is_drug_user = models.CharField(max_length=10, blank=True, null=True)
    high_risk_activities = models.CharField(max_length=10, blank=True, null=True)
    
    # PWD
    pwd_toggle = models.CharField(max_length=10, blank=True, null=True)
    is_pwd = models.TextField(blank=True, null=True)
    
    # Buntis
    
    buntis_toggle = models.CharField(max_length=10, blank=True, null=True)  # Add buntis_toggle field
    pregnancy_order = models.CharField(max_length=50, blank=True, null=True)
    birth_plan = models.CharField(max_length=50, blank=True, null=True)
    prenatal_checkup = models.CharField(max_length=50, blank=True, null=True)
    prenatal_location = models.CharField(max_length=100, blank=True, null=True)
    prenatal_provider = models.CharField(max_length=100, blank=True, null=True)
    
    
    barangay = models.CharField(max_length=100, blank=True, null=True)  # Add barangay field

    def save(self, *args, **kwargs):
        if self.household and not self.barangay:
            self.barangay = self.household.barangay  # Automatically set barangay from Household
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class PersonData(models.Model):
    person = models.ForeignKey('Person', on_delete=models.CASCADE)
    year = models.IntegerField()  # Add this field to store the year
    data = models.JSONField()  # Store other data as JSON or use individual fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)  # Track active/inactive status
