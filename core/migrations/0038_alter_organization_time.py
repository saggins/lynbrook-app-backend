# Generated by Django 3.2.5 on 2021-09-04 22:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0037_organization_location'),
    ]

    operations = [
        migrations.AlterField(
            model_name='organization',
            name='time',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
    ]
