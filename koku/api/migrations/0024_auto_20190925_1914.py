# Generated by Django 2.2.4 on 2019-09-25 19:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0023_auto_20190923_1810'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sources',
            name='auth_header',
            field=models.TextField(null=True),
        ),
    ]
