# Generated by Django 5.1.5 on 2025-02-01 14:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0019_alter_user_project_start_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='projects',
            name='url',
            field=models.URLField(blank=True, null=True),
        ),
    ]
