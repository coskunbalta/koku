# Generated by Django 2.2.6 on 2019-12-03 02:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0040_auto_20191121_2154'),
    ]

    operations = [
        migrations.AddField(
            model_name='sources',
            name='account_id',
            field=models.CharField(max_length=150, null=True),
        ),
    ]
