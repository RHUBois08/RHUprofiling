# Generated by Django 5.1.7 on 2025-05-01 05:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0025_remove_person_adult_booster_brand_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='newborn_immunization',
            field=models.CharField(blank=True, max_length=30, null=True),
        ),
    ]
