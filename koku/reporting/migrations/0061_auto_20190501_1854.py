# Generated by Django 2.2 on 2019-05-01 18:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0060_auto_20190430_1926'),
    ]

    operations = [
        migrations.AddField(
            model_name='awscostentrylineitemdaily',
            name='cost_entry_bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='reporting.AWSCostEntryBill'),
        ),
        migrations.AddField(
            model_name='awscostentrylineitemdailysummary',
            name='cost_entry_bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='reporting.AWSCostEntryBill'),
        ),
        migrations.AddField(
            model_name='ocpawscostlineitemdailysummary',
            name='cost_entry_bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='reporting.AWSCostEntryBill'),
        ),
        migrations.AddField(
            model_name='ocpawscostlineitemprojectdailysummary',
            name='cost_entry_bill',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='reporting.AWSCostEntryBill'),
        ),
    ]