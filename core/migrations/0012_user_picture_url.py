# Generated by Django 3.2.5 on 2021-08-06 08:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_auto_20210805_2319'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='picture_url',
            field=models.URLField(default='https://upload.wikimedia.org/wikipedia/commons/7/7c/Profile_avatar_placeholder_large.png'),
        ),
    ]
