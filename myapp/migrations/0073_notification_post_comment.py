# Generated by Django 5.1.5 on 2025-03-23 09:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0072_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='post_comment',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='myapp.post_comments'),
        ),
    ]
