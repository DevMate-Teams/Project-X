# Generated by Django 5.1.5 on 2025-02-02 06:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0021_project_comment_project_reply'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projects',
            name='skill_needed',
            field=models.ManyToManyField(related_name='projects', to='myapp.skill'),
        ),
    ]
