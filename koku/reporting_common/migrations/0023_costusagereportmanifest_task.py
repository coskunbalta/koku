# Generated by Django 2.2.4 on 2019-10-31 19:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting_common', '0022_add_gcp_column_maps'),
    ]

    operations = [
        migrations.AddField(
            model_name='costusagereportmanifest',
            name='task',
            field=models.UUIDField(null=True),
        ),
    ]
