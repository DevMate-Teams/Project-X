# Generated by Django 5.1.5 on 2025-02-02 06:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0022_alter_projects_skill_needed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projects',
            name='domain',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='projects', to='myapp.domain'),
        ),
    ]
