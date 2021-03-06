# Generated by Django 2.2.4 on 2019-09-23 14:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting_common', '0016_auto_20190829_2053'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reportcolumnmap',
            name='provider_type',
            field=models.CharField(choices=[('AWS', 'AWS'), ('OCP', 'OCP'), ('AZURE', 'AZURE'), ('GCP', 'GCP'), ('AWS-local', 'AWS-local'), ('AZURE-local', 'AZURE-local'), ('GCP-local', 'GCP-local')], default='AWS', max_length=50),
        ),
    ]
