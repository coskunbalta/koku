# Generated by Django 2.1.2 on 2018-11-29 02:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reporting', '0017_auto_20181121_1444'),
    ]

    operations = [
        migrations.RenameField(
            model_name='ocpusagelineitemdailysummary',
            old_name='pod_charge_cpu_cores',
            new_name='pod_charge_cpu_core_hours',
        ),
        migrations.RenameField(
            model_name='ocpusagelineitemdailysummary',
            old_name='pod_charge_memory_gigabytes',
            new_name='pod_charge_memory_gigabyte_hours',
        ),
        migrations.RenameField(
            model_name='ocpusagelineitemdailysummary',
            old_name='pod_limit_memory_gigabytes',
            new_name='pod_limit_memory_gigabyte_hours',
        ),
        migrations.RenameField(
            model_name='ocpusagelineitemdailysummary',
            old_name='pod_request_memory_gigabytes',
            new_name='pod_request_memory_gigabyte_hours',
        ),
        migrations.RenameField(
            model_name='ocpusagelineitemdailysummary',
            old_name='pod_usage_memory_gigabytes',
            new_name='pod_usage_memory_gigabyte_hours',
        ),
        migrations.RemoveField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_memory_byte_hours',
        ),
        migrations.RemoveField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_memory_bytes',
        ),
        migrations.AddField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_memory_gigabyte_hours',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AddField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_memory_gigabytes',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='node_capacity_cpu_core_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='node_capacity_cpu_cores',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='node_capacity_memory_byte_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='node_capacity_memory_bytes',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_limit_cpu_core_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_limit_memory_byte_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_request_cpu_core_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_request_memory_byte_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_usage_cpu_core_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitem',
            name='pod_usage_memory_byte_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdaily',
            name='node_capacity_cpu_core_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdaily',
            name='node_capacity_cpu_cores',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdaily',
            name='node_capacity_memory_byte_seconds',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdaily',
            name='node_capacity_memory_bytes',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_cpu_core_hours',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
        migrations.AlterField(
            model_name='ocpusagelineitemdailysummary',
            name='node_capacity_cpu_cores',
            field=models.DecimalField(decimal_places=6, max_digits=24, null=True),
        ),
    ]