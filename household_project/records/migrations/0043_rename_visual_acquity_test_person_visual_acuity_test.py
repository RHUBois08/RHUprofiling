# Generated by Django 5.1.7 on 2025-05-21 02:49

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0042_rename_fourteen49_cervical_cancer_screening_person_cervical_cancer_screening_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='person',
            old_name='visual_acquity_test',
            new_name='visual_acuity_test',
        ),
    ]
