# Generated by Django 2.2.4 on 2019-11-11 19:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0082_auto_20191107_1541'),
    ]

    operations = [
        migrations.AlterField(
            model_name='costsummary',
            name='infra_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='costsummary',
            name='project_infra_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemdailysummary',
            name='markup_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemdailysummary',
            name='unblended_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemprojectdailysummary',
            name='pod_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemprojectdailysummary',
            name='project_markup_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemprojectdailysummary',
            name='unblended_cost',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpawscostlineitemprojectdailysummary',
            name='usage_amount',
            field=models.DecimalField(decimal_places=15, max_digits=30, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdailysummary',
            name='infra_cost',
            field=models.DecimalField(decimal_places=15, max_digits=33, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdailysummary',
            name='project_infra_cost',
            field=models.DecimalField(decimal_places=15, max_digits=33, null=True),
        ),
    ]
