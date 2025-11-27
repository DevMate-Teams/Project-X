from django.db import migrations

def populate_logos(apps, schema_editor):
    CodingStyle = apps.get_model('myapp', 'CodingStyle')
    
    mapping = {
        'Coffee Coder': 'coffee-coder.svg',
        'Debug Duck': 'debug-duck.svg',
        'Terminal Samurai': 'terminal-samurai.svg',
        'Zen Refactorer': 'zen-refactorer.svg',
        'Error Collector': 'error-collector.svg',
        'Night Owl': 'night-owl.svg',
        'Precision Sprinter': 'precision-sprinter.svg',
        'Team Player': 'team-player.svg'
    }
    
    for style in CodingStyle.objects.all():
        if style.name in mapping:
            style.logo = mapping[style.name]
            style.save()

class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0121_codingstyle_logo'),
    ]

    operations = [
        migrations.RunPython(populate_logos),
    ]
