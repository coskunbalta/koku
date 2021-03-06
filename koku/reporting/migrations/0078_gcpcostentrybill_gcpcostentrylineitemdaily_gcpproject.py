# Generated by Django 2.2.4 on 2019-10-29 13:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0033_auto_20191022_1635'),
        ('reporting', '0077_auto_20191026_2002'),
    ]

    operations = [
        migrations.CreateModel(
            name='GCPCostEntryBill',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('billing_period_start', models.DateTimeField()),
                ('billing_period_end', models.DateTimeField()),
                ('summary_data_creation_datetime', models.DateTimeField(blank=True, null=True)),
                ('summary_data_updated_datetime', models.DateTimeField(blank=True, null=True)),
                ('finalized_datetime', models.DateTimeField(blank=True, null=True)),
                ('derived_cost_datetime', models.DateTimeField(blank=True, null=True)),
                ('provider', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Provider')),
            ],
            options={
                'unique_together': {('billing_period_start', 'provider')},
            },
        ),
        migrations.CreateModel(
            name='GCPProject',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_id', models.CharField(max_length=20)),
                ('project_number', models.BigIntegerField()),
                ('project_id', models.CharField(max_length=256, unique=True)),
                ('project_name', models.CharField(max_length=256)),
                ('project_labels', models.CharField(blank=True, max_length=256, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='GCPCostEntryLineItemDaily',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('line_item_type', models.CharField(max_length=256)),
                ('measurement_type', models.CharField(max_length=512)),
                ('consumption', models.BigIntegerField()),
                ('unit', models.CharField(blank=True, max_length=63, null=True)),
                ('cost', models.DecimalField(blank=True, decimal_places=9, max_digits=17, null=True)),
                ('currency', models.CharField(max_length=10)),
                ('description', models.CharField(blank=True, max_length=256, null=True)),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('cost_entry_bill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='reporting.GCPCostEntryBill')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='reporting.GCPProject')),
            ],
            options={
                'unique_together': {('start_time', 'line_item_type', 'project')},
            },
        ),
    ]
