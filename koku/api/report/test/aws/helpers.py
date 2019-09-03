#
# Copyright 2019 Red Hat, Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
"""Populate test data for AWS reports."""
import copy
import random
import re
from decimal import Decimal

from django.contrib.postgres.aggregates import ArrayAgg
from django.db import connection
from django.db.models import Count, DateTimeField, Max, Sum, Value
from django.db.models.functions import Cast, Concat
from faker import Faker
from tenant_schemas.utils import tenant_context

from api.utils import DateHelper
from reporting.models import (AWSAccountAlias,
                              AWSCostEntry,
                              AWSCostEntryBill,
                              AWSCostEntryLineItem,
                              AWSCostEntryLineItemDaily,
                              AWSCostEntryLineItemDailySummary,
                              AWSCostEntryPricing,
                              AWSCostEntryProduct)


class AWSReportDataGenerator(object):
    """Object to generate and store fake AWS cost data."""

    fake = Faker()
    dh = DateHelper()

    SOME_INSTANCE_TYPES = ['t3.small', 't3.medium', 't3.large',
                           'm5.large', 'm5.xlarge', 'm5.2xlarge',
                           'c5.large', 'c5.xlarge', 'c5.2xlarge',
                           'r5.large', 'r5.xlarge', 'r5.2xlarge']

    SOME_REGIONS = ['us-east-2', 'us-east-1',
                    'us-west-1', 'us-west-2',
                    'ap-south-1',
                    'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
                    'ap-southeast-1', 'ap-southeast-2',
                    'ca-central-1',
                    'eu-central-1',
                    'eu-west-1', 'eu-west-2', 'eu-west-3',
                    'sa-east-1']

    def __init__(self, account_alias=None, account_id=None,
                 availability_zone=None, bill=None,
                 billing_period_end=None, billing_period_start=None,
                 cost_entry=None, instance_type=None, line_item=None,
                 pricing=None, region=None, usage_end=None, usage_start=None,
                 resource_id=None):
        """Constructor."""
        # properties
        self._account_alias = account_alias
        self._account_id = account_id
        self._availability_zone = availability_zone
        self._bill = bill
        self._billing_period_end = billing_period_end
        self._billing_period_start = billing_period_start
        self._cost_entry = cost_entry
        self._instance_type = instance_type
        self._line_item = line_item
        self._pricing = pricing
        self._region = region
        self._usage_end = usage_end
        self._usage_start = usage_start
        self._resource_id = resource_id
        self.current_month_total = Decimal(0)

        self._products = {'fake': {'sku': self.fake.pystr(min_chars=12,
                                                          max_chars=12).upper(),
                                   'product_name': self.fake.words(nb=5),
                                   'product_family': self.fake.words(nb=3),
                                   'service_code': self.fake.word(),
                                   'region': self.region,
                                   'instance_type': self.instance_type,
                                   'memory': random.randint(1, 100),
                                   'vcpu': random.randint(1, 100)},

                          'ec2': {'sku': self.fake.pystr(min_chars=12,
                                                         max_chars=12).upper(),
                                  'product_name': 'Amazon Elastic Compute Cloud',
                                  'product_family': 'Compute Instance',
                                  'service_code': 'AmazonEC2',
                                  'region': self.region,
                                  'instance_type': self.instance_type,
                                  'memory': random.choice([8, 16, 32, 64]),
                                  'vcpu': random.choice([2, 4, 8, 16])},

                          'ebs': {'sku': self.fake.pystr(min_chars=12,
                                                         max_chars=12).upper(),
                                  'product_name': 'Amazon Elastic Compute Cloud',
                                  'product_family': 'Storage',
                                  'service_code': 'AmazonEC2',
                                  'region': self.region}}

        short_region = self._usage_transform(self.region)
        self.SOME_USAGE_OPERATIONS = {'ec2': [(f'BoxUsage:{self.region}', 'RunInstances'),
                                              ('DataTransfer-In-Bytes', 'RunInstances'),
                                              ('DataTransfer-Out-Bytes', 'RunInstances'),
                                              (f'{short_region}-DataTransfer-In-Bytes', 'RunInstances'),
                                              (f'{short_region}-DataTransfer-Out-Bytes', 'RunInstances')],
                                      'ebs': [('EBS:VolumeUsage.gp2', 'CreateVolume-Gp2'),
                                              ('EBS:VolumeUsage', 'CreateVolume'),
                                              (f'{short_region}-EBS:VolumeUsage', 'CreateVolume'),
                                              (f'{short_region}-EBS:VolumeUsage.gp2', 'CreateVolume-Gp2'),
                                              ('EBS:SnapshotUsage', 'CreateSnapshot')]}

    def __str__(self):
        """Represent data as string."""
        return str(self.to_dict())

    def _usage_transform(self, region):
        """Translate region into shortened string used in usage.

        Example: 'us-east-1' becomes 'USE1'

        Note: Real-world line items can be formatted using 'EUC1' or 'EU', depending
              on the context. Additional work will be required to support the
              second format.
        """
        regex = r'(\w+)-(\w+)-(\d+)'
        groups = re.search(regex, region).groups()
        output = '{}{}{}'.format(groups[0].upper(),
                                 groups[1][0].upper(),
                                 groups[2])
        return output

    @property
    def account_alias(self):
        """Randomly generated account alias."""
        if not self._account_alias:
            self._account_alias = self.fake.company()
        return self._account_alias

    @account_alias.setter
    def account_alias(self, alias):
        """Account alias setter."""
        self._account_alias = alias

    @property
    def account_id(self):
        """Randomly generated account id."""
        if not self._account_id:
            self._account_id = self.fake.ean(length=13)  # pylint: disable=no-member
        return self._account_id

    @account_id.setter
    def account_id(self, account_id):
        """Account id setter."""
        self._account_id = account_id
        if self.bill:
            self.bill['payer_account_id'] = account_id
        if self._line_item:
            self._line_item['usage_account_id'] = account_id

    @property
    def availability_zone(self):
        """Availability zone."""
        if not self._availability_zone:
            self._availability_zone = self.region + random.choice(['a', 'b', 'c'])
        return self._availability_zone

    @availability_zone.setter
    def availability_zone(self, zone):
        """Availability zone."""
        self._availability_zone = zone
        if self._line_item:
            self._line_item['availability_zone'] = zone

    @property
    def bill(self):
        """Bill."""
        if not self._bill:
            self._bill = {'bill_type': 'Anniversary',
                          'payer_account_id': self.account_id,
                          'billing_period_start': self.billing_period_start,
                          'billing_period_end': self.billing_period_end}
        return self._bill

    @bill.setter
    def bill(self, obj):
        """Bill setter."""
        self._bill = obj

    @property
    def billing_period_end(self):
        """Billing period end date."""
        if not self._billing_period_end:
            self._billing_period_end = self.dh.this_month_end
        return self._billing_period_end

    @billing_period_end.setter
    def billing_period_end(self, date):
        """Billing period end date setter."""
        self._billing_period_end = date
        if self.bill:
            self.bill['billing_period_end'] = date
        if self.cost_entry:
            self.cost_entry['interval_end'] = date

    @property
    def billing_period_start(self):
        """Billing period start date."""
        if not self._billing_period_start:
            self._billing_period_start = self.dh.this_month_start
        return self._billing_period_start

    @billing_period_start.setter
    def billing_period_start(self, date):
        """Billing period start date setter."""
        self._billing_period_start = date
        if self.bill:
            self.bill['billing_period_start'] = date
        if self.cost_entry:
            self.cost_entry['interval_start'] = date

    @property
    def cost_entry(self):
        """Cost entry."""
        if not self._cost_entry:
            self._cost_entry = {'interval_start': self.billing_period_start,
                                'interval_end': self.billing_period_end,
                                'bill': self.bill}
        return self._cost_entry

    @cost_entry.setter
    def cost_entry(self, obj):
        """Cost entry setter."""
        self._cost_entry = obj

    @property
    def instance_type(self):
        """Randomly selected instance type."""
        if not self._instance_type:
            self._instance_type = random.choice(self.SOME_INSTANCE_TYPES)
        return self._instance_type

    @instance_type.setter
    def instance_type(self, instance_type):
        """Instance type setter."""
        self._instance_type = instance_type
        for prod in self._products:
            self._products[prod]['instance_type'] = instance_type
        if self._line_item:
            self._line_item['cost_entry_product']['instance_type'] = instance_type

    def line_item(self, product='ec2'):
        """Fake line item.

        Args:
            product (string) Either 'ec2' or 'ebs'

        """
        if not self._line_item:
            usage = random.randint(1, 100)
            ub_rate = random.random()
            b_rate = random.random()
            usage_type, operation = random.choice(self.SOME_USAGE_OPERATIONS[product])

            self._line_item = {'invoice_id': self.fake.sha1(raw_output=False),
                               'availability_zone': self.availability_zone,
                               'blended_cost': b_rate * usage,
                               'blended_rate': b_rate,
                               'cost_entry': self.cost_entry,
                               'cost_entry_bill': self.bill,
                               'cost_entry_pricing': self.pricing,
                               'cost_entry_product': self.product(product),
                               'currency_code': 'USD',
                               'line_item_type': 'Usage',
                               'operation': operation,
                               'product_code': 'AmazonEC2',
                               'resource_id': 'i-{}'.format(self.resource_id),
                               'usage_amount': usage,
                               'unblended_cost': ub_rate * usage,
                               'unblended_rate': ub_rate,
                               'usage_account_id': self.account_id,
                               'usage_end': self.usage_end,
                               'usage_start': self.usage_start,
                               'usage_type': usage_type,
                               'tags': self._get_tags()
                               }
        return self._line_item

    @property
    def pricing(self):
        """Product pricing."""
        if not self._pricing:
            self._pricing = {'term': 'OnDemand',
                             'unit': 'Hrs'}
        return self._pricing

    @pricing.setter
    def pricing(self, obj):
        """Pricing setter."""
        self._pricing = obj
        if self._line_item:
            self._line_item['cost_entry_pricing'] = obj

    def product(self, product='ec2'):
        """Product."""
        return self._products.get(product, self._products['fake'])

    @property
    def region(self):
        """Randomly selected region."""
        if not self._region:
            self._region = random.choice(self.SOME_REGIONS)
        return self._region

    @region.setter
    def region(self, region):
        """Region setter."""
        self._region = region
        for prod in self._products:
            self._products[prod]['region'] = region
        if self._line_item:
            self._line_item['cost_entry_product']['region'] = region

    def to_dict(self):
        """Return a copy of object data as a dict."""
        return {'account_alias': self.account_alias,
                'account_id': self.account_id,
                'availability_zone': self.availability_zone,
                'bill': self.bill,
                'billing_period_end': self.billing_period_end,
                'billing_period_start': self.billing_period_start,
                'cost_entry': self.cost_entry,
                'instance_type': self.instance_type,
                'line_item': self.line_item(),
                'pricing': self.pricing,
                'region': self.region,
                'usage_end': self.usage_end,
                'usage_start': self.usage_start}

    @property
    def usage_end(self):
        """Usage end date."""
        if not self._usage_end:
            self._usage_end = self.dh.this_month_start + self.dh.one_day
        return self._usage_end

    @usage_end.setter
    def usage_end(self, date):
        """Usage end date setter."""
        self._usage_end = date
        if self._line_item:
            self._line_item['usage_end'] = date

    @property
    def resource_id(self):
        """resource_id."""
        if not self._resource_id:
            self._resource_id = self.fake.ean8()
        return self._resource_id

    @property
    def usage_start(self):
        """Usage start date."""
        if not self._usage_start:
            self._usage_start = self.dh.this_month_start
        return self._usage_start

    @usage_start.setter
    def usage_start(self, date):
        """Usage start date setter."""
        self._usage_start = date
        if self._line_item:
            self._line_item['usage_start'] = date

    def _get_tags(self):
        """Create tags for output data."""
        apps = [self.fake.word(), self.fake.word(), self.fake.word(),  # pylint: disable=no-member
                self.fake.word(), self.fake.word(), self.fake.word()]  # pylint: disable=no-member
        organizations = [self.fake.word(), self.fake.word(),  # pylint: disable=no-member
                         self.fake.word(), self.fake.word()]  # pylint: disable=no-member
        markets = [self.fake.word(), self.fake.word(), self.fake.word(),  # pylint: disable=no-member
                   self.fake.word(), self.fake.word(), self.fake.word()]  # pylint: disable=no-member
        versions = [self.fake.word(), self.fake.word(), self.fake.word(),  # pylint: disable=no-member
                    self.fake.word(), self.fake.word(), self.fake.word()]  # pylint: disable=no-member

        seeded_labels = {'environment': ['dev', 'ci', 'qa', 'stage', 'prod'],
                         'app': apps,
                         'organization': organizations,
                         'market': markets,
                         'version': versions
                         }
        gen_label_keys = [self.fake.word(), self.fake.word(), self.fake.word(),  # pylint: disable=no-member
                          self.fake.word(), self.fake.word(), self.fake.word()]  # pylint: disable=no-member
        all_label_keys = list(seeded_labels.keys()) + gen_label_keys
        num_labels = random.randint(2, len(all_label_keys))
        chosen_label_keys = random.choices(all_label_keys, k=num_labels)

        labels = {}
        for label_key in chosen_label_keys:
            label_value = self.fake.word()  # pylint: disable=no-member
            if label_key in seeded_labels:
                label_value = random.choice(seeded_labels[label_key])

            labels['{}_label'.format(label_key)] = label_value

        return labels

    def add_data_to_tenant(self, data, product='ec2'):
        """Populate tenant with AWS data."""
        with tenant_context(data):
            # get or create alias
            AWSAccountAlias.objects.get_or_create(
                account_id=self._account_id,
                account_alias=self._account_alias)

            # create bill
            bill, _ = AWSCostEntryBill.objects.get_or_create(**self._bill)

            # create ec2 product
            product_data = self.product(product)
            ce_product, _ = AWSCostEntryProduct.objects.get_or_create(**product_data)

            # create pricing
            ce_pricing, _ = AWSCostEntryPricing.objects.get_or_create(**self._pricing)

            # add hourly data
            data_start = self._usage_start
            data_end = self._usage_end
            current = data_start

            while current < data_end:
                end_hour = current + DateHelper().one_hour

                # generate copy of data with 1 hour usage range.
                curr_data = copy.deepcopy(self)
                curr_data.usage_end = end_hour
                curr_data.usage_start = current

                # keep line items within the same AZ
                curr_data.availability_zone = self._availability_zone

                # get or create cost entry
                cost_entry_data = curr_data.cost_entry
                cost_entry_data.update({'bill': bill})
                cost_entry, _ = AWSCostEntry.objects.get_or_create(**cost_entry_data)

                # create line item
                line_item_data = curr_data.line_item(product)
                model_instances = {'cost_entry': cost_entry,
                                   'cost_entry_bill': bill,
                                   'cost_entry_product': ce_product,
                                   'cost_entry_pricing': ce_pricing}
                line_item_data.update(model_instances)

                line_item, _ = AWSCostEntryLineItem.objects.get_or_create(**line_item_data)

                current = end_hour

            self._populate_daily_table()
            self._populate_daily_summary_table()
            self._populate_tag_summary_table()

    def _populate_daily_table(self):
        included_fields = [
            'cost_entry_product_id',
            'cost_entry_pricing_id',
            'cost_entry_reservation_id',
            'line_item_type',
            'usage_account_id',
            'usage_type',
            'operation',
            'availability_zone',
            'resource_id',
            'tax_type',
            'product_code',
            'tags'
        ]
        annotations = {
            'usage_start': Cast('usage_start', DateTimeField()),
            'usage_end': Cast('usage_start', DateTimeField()),
            'usage_amount': Sum('usage_amount'),
            'normalization_factor': Max('normalization_factor'),
            'normalized_usage_amount': Sum('normalized_usage_amount'),
            'currency_code': Max('currency_code'),
            'unblended_rate': Max('unblended_rate'),
            'unblended_cost': Sum('unblended_cost'),
            'blended_rate': Max('blended_rate'),
            'blended_cost': Sum('blended_cost'),
            'public_on_demand_cost': Sum('public_on_demand_cost'),
            'public_on_demand_rate': Max('public_on_demand_rate')
        }

        entries = AWSCostEntryLineItem.objects\
            .values(*included_fields)\
            .annotate(**annotations)
        for entry in entries:
            daily = AWSCostEntryLineItemDaily(**entry)
            daily.save()

    def remove_data_from_tenant(self):
        """Remove the added data."""
        with tenant_context(self):
            for table in (AWSAccountAlias,
                          AWSCostEntryLineItem,
                          AWSCostEntryLineItemDaily,
                          AWSCostEntryLineItemDailySummary,
                          ):
                table.objects.all().delete()

    def _populate_daily_summary_table(self):
        included_fields = [
            'usage_start',
            'usage_end',
            'usage_account_id',
            'availability_zone',
            'tags'
        ]
        annotations = {
            'product_family': Concat('cost_entry_product__product_family', Value('')),
            'product_code': Concat('cost_entry_product__service_code', Value('')),
            'region': Concat('cost_entry_product__region', Value('')),
            'instance_type': Concat('cost_entry_product__instance_type', Value('')),
            'unit': Concat('cost_entry_pricing__unit', Value('')),
            'usage_amount': Sum('usage_amount'),
            'normalization_factor': Max('normalization_factor'),
            'normalized_usage_amount': Sum('normalized_usage_amount'),
            'currency_code': Max('currency_code'),
            'unblended_rate': Max('unblended_rate'),
            'unblended_cost': Sum('unblended_cost'),
            'blended_rate': Max('blended_rate'),
            'blended_cost': Sum('blended_cost'),
            'public_on_demand_cost': Sum('public_on_demand_cost'),
            'public_on_demand_rate': Max('public_on_demand_rate'),
            'resource_count': Count('resource_id', distinct=True),
            'resource_ids': ArrayAgg('resource_id', distinct=True)
        }

        entries = AWSCostEntryLineItemDaily.objects\
            .values(*included_fields)\
            .annotate(**annotations)
        for entry in entries:
            alias = AWSAccountAlias.objects.filter(account_id=entry['usage_account_id'])
            summary = AWSCostEntryLineItemDailySummary(**entry,
                                                       account_alias=list(alias).pop())
            summary.save()
            self.current_month_total += entry['unblended_cost']

    def _populate_tag_summary_table(self):
        """Populate pod label key and values."""
        raw_sql = """
            INSERT INTO reporting_awstags_summary
            SELECT l.key,
                array_agg(DISTINCT l.value) as values
            FROM (
                SELECT key,
                    value
                FROM reporting_awscostentrylineitem_daily AS li,
                    jsonb_each_text(li.tags) labels
            ) l
            GROUP BY l.key
            ON CONFLICT (key) DO UPDATE
            SET values = EXCLUDED.values
        """

        with connection.cursor() as cursor:
            cursor.execute(raw_sql)
