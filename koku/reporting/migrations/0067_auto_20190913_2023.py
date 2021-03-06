# Generated by Django 2.2.4 on 2019-09-13 20:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0066_auto_20190913_1734'),
    ]

    operations = [
        migrations.AddField(
            model_name='awscostentrylineitemdailysummary',
            name='markup_cost',
            field=models.DecimalField(decimal_places=9, max_digits=17, null=True),
        ),
        migrations.AddField(
            model_name='azurecostentrylineitemdailysummary',
            name='markup_cost',
            field=models.DecimalField(decimal_places=9, max_digits=17, null=True),
        ),
        migrations.AddField(
            model_name='costsummary',
            name='markup_cost',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AddField(
            model_name='costsummary',
            name='project_markup_cost',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
    ]
