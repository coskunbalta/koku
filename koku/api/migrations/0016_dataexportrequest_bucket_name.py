# Generated by Django 2.2.4 on 2019-08-22 15:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0015_dataexportrequest'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataexportrequest',
            name='bucket_name',
            field=models.CharField(default='', max_length=63),
            preserve_default=False,
        ),
    ]
