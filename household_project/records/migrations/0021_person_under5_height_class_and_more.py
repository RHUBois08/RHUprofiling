# Generated by Django 5.1.7 on 2025-04-30 00:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('records', '0020_remove_person_under5_nutrition_person_under5_height_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='under5_height_class',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name='person',
            name='under5_weight_class',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
