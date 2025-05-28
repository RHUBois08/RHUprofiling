from django.db import migrations

def set_default_json_fields(apps, schema_editor):
    Person = apps.get_model('records', 'Person')
    for person in Person.objects.all():
        if person.senior_flu_vaccine is None or person.senior_flu_vaccine == '':
            person.senior_flu_vaccine = []
        if person.senior_pneumonia_vaccine is None or person.senior_pneumonia_vaccine == '':
            person.senior_pneumonia_vaccine = []
        person.save()

class Migration(migrations.Migration):

    dependencies = [
        ('records', '0022_rename_five9_immunization_person_five19_immunization_and_more'),
    ]

    operations = [
        migrations.RunPython(set_default_json_fields),
    ]