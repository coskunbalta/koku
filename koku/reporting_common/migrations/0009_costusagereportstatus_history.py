# Generated by Django 2.2 on 2019-05-07 16:25

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('reporting_common', '0008_auto_20190412_1330'),
    ]

    operations = [
        migrations.AddField(
            model_name='costusagereportstatus',
            name='history',
            field=django.contrib.postgres.fields.jsonb.JSONField(null=True),
        ),
    ]
