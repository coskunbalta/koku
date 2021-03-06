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
"""Test the Report Queries."""

from decimal import Decimal, ROUND_HALF_UP
from unittest.mock import PropertyMock, patch

from dateutil.relativedelta import relativedelta
from django.db.models import F, Sum
from django.urls import reverse
from tenant_schemas.utils import tenant_context

from api.iam.test.iam_test_case import IamTestCase
from api.models import Provider
from api.provider.test import create_generic_provider
from api.query_filter import QueryFilter
from api.report.azure.openshift.query_handler import OCPAzureReportQueryHandler
from api.report.azure.openshift.view import (
    OCPAzureCostView,
    OCPAzureInstanceTypeView,
    OCPAzureStorageView,
)
from api.report.test.azure.helpers import AZURE_SERVICES
from api.report.test.azure.openshift.helpers import OCPAzureReportDataGenerator
from api.utils import DateHelper
from reporting.models import OCPAzureCostLineItemDailySummary


class OCPAWSQueryHandlerTestNoData(IamTestCase):
    """Tests for the OCP report query handler with no data."""

    def setUp(self):
        """Set up the customer view tests."""
        super().setUp()
        self.dh = DateHelper()

        self.this_month_filter = {'usage_start__gte': self.dh.this_month_start}
        self.ten_day_filter = {'usage_start__gte': self.dh.n_days_ago(self.dh.today, 9)}
        self.thirty_day_filter = {
            'usage_start__gte': self.dh.n_days_ago(self.dh.today, 29)
        }
        self.last_month_filter = {
            'usage_start__gte': self.dh.last_month_start,
            'usage_end__lte': self.dh.last_month_end,
        }

    def test_execute_sum_query_instance_types(self):
        """Test that the sum query runs properly for instance-types."""
        url = '?'
        query_params = self.mocked_query_params(url, OCPAzureInstanceTypeView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        keys_units = {
            'cost': 'USD',
            'markup_cost': 'USD',
            'usage': 'Instance Type Placeholder',
            'count': 'instances',
        }
        for key, unit in keys_units.items():
            self.assertIsNotNone(total.get(key))
            self.assertIsInstance(total.get(key), dict)
            self.assertEqual(total.get(key).get('value'), 0)
            self.assertEqual(total.get(key).get('units'), unit)


class OCPAzureQueryHandlerTest(IamTestCase):
    """Tests for the OCP report query handler."""

    def setUp(self):
        """Set up the customer view tests."""
        super().setUp()
        self.dh = DateHelper()
        _, self.provider = create_generic_provider(Provider.PROVIDER_OCP, self.headers)

        self.this_month_filter = {'usage_start__gte': self.dh.this_month_start}
        self.ten_day_filter = {'usage_start__gte': self.dh.n_days_ago(self.dh.today, 9)}
        self.thirty_day_filter = {
            'usage_start__gte': self.dh.n_days_ago(self.dh.today, 29)
        }
        self.last_month_filter = {
            'usage_start__gte': self.dh.last_month_start,
            'usage_end__lte': self.dh.last_month_end,
        }
        self.generator = OCPAzureReportDataGenerator(self.tenant, self.provider)

    def get_totals_by_time_scope(self, aggregates, filters=None):
        """Return the total aggregates for a time period."""
        if filters is None:
            filters = self.ten_day_filter
        with tenant_context(self.tenant):
            return OCPAzureCostLineItemDailySummary.objects.filter(**filters).aggregate(
                **aggregates
            )

    def test_execute_sum_query_storage(self):
        """Test that the sum query runs properly."""
        self.generator.add_data_to_tenant(service_name='Storage')
        url = '?'
        query_params = self.mocked_query_params(url, OCPAzureStorageView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))

        aggregates = handler._mapper.report_type_map.get('aggregates')
        filt = {'service_name__contains': 'Storage'}
        filt.update(self.ten_day_filter)
        current_totals = self.get_totals_by_time_scope(aggregates, filt)
        total = query_output.get('total')
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

    def test_execute_sum_query_instance_types(self):
        """Test that the sum query runs properly."""
        self.generator.add_data_to_tenant()
        url = '?'
        query_params = self.mocked_query_params(url, OCPAzureInstanceTypeView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))

        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(aggregates, self.ten_day_filter)
        total = query_output.get('total')
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

    def test_execute_query_current_month_daily(self):
        """Test execute_query for current month on daily breakdown."""
        self.generator.add_data_to_tenant()
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=daily'
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))

        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

    def test_execute_query_current_month_by_account(self):
        """Test execute_query for current month on monthly breakdown by account."""
        self.generator.add_data_to_tenant()
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))

        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('subscription_guids')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_current_month_by_service(self):
        """Test execute_query for current month on monthly breakdown by service."""
        self.generator.add_data_to_tenant()

        valid_services = list(AZURE_SERVICES.keys())
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[service_name]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('service_names')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                name = month_item.get('service_name')
                self.assertIn(name, valid_services)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_by_filtered_service(self):
        """Test execute_query monthly breakdown by filtered service."""
        self.generator.add_data_to_tenant(
            fixed_fields=[
                'subscription_guid',
                'resource_location',
                'tags',
                'service_name',
            ]
        )

        valid_services = list(AZURE_SERVICES.keys())
        service = self.generator.config.service_name
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[service_name]={service}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        filters = {**self.this_month_filter, 'service_name__icontains': service}
        for filt in handler._mapper.report_type_map.get('filter'):
            if filt:
                qf = QueryFilter(**filt)
                filters.update({qf.composed_query_string(): qf.parameter})
        current_totals = self.get_totals_by_time_scope(aggregates, filters)
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('service_names')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                name = month_item.get('service_name')
                self.assertIn(name, valid_services)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_curr_month_by_subscription_guid_w_limit(self):
        """Test execute_query for current month on monthly breakdown by subscription_guid with limit."""
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[limit]=2&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('subscription_guids')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(2, len(month_data))
            for month_item in month_data:
                self.assertIsInstance(month_item.get('subscription_guid'), str)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_curr_month_by_subscription_guid_w_order(self):
        """Test execute_query for current month on monthly breakdown by subscription_guid with asc order."""
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&order_by[cost]=asc&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('subscription_guids')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(len(month_data), 2)
            current_total = 0
            for month_item in month_data:
                self.assertIsInstance(month_item.get('subscription_guid'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(
                    month_item.get('values')[0].get('cost', {}).get('value')
                )
                data_point_total = (
                    month_item.get('values')[0].get('cost', {}).get('value')
                )
                self.assertLess(current_total, data_point_total)
                current_total = data_point_total

    def test_execute_query_curr_month_by_subscription_guid_w_order_by_subscription_guid(
        self
    ):
        """Test execute_query for current month on monthly breakdown by subscription_guid with asc order."""
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&order_by[subscription_guid]=asc&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('subscription_guids')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(len(month_data), 2)
            current = '0'
            for month_item in month_data:
                self.assertIsInstance(month_item.get('subscription_guid'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(
                    month_item.get('values')[0].get('subscription_guid')
                )
                data_point = month_item.get('values')[0].get('subscription_guid')
                if data_point == '1 Other':
                    continue
                self.assertLess(current, data_point)
                current = data_point

    def test_execute_query_curr_month_by_cluster(self):
        """Test execute_query for current month on monthly breakdown by group_by cluster."""
        self.generator.add_data_to_tenant()
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[cluster]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('clusters')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('cluster'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_by_filtered_cluster(self):
        """Test execute_query monthly breakdown by filtered cluster."""
        self.generator.add_data_to_tenant()

        cluster = self.generator.cluster_id
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[cluster]={cluster}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        filters = {**self.this_month_filter, 'cluster_id__icontains': cluster}
        for filt in handler._mapper.report_type_map.get('filter'):
            if filt:
                qf = QueryFilter(**filt)
                filters.update({qf.composed_query_string(): qf.parameter})
        current_totals = self.get_totals_by_time_scope(aggregates, filters)
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('clusters')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('cluster'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_curr_month_by_filtered_resource_location(self):
        """Test execute_query for current month on monthly breakdown by filtered resource_location."""
        self.generator.add_data_to_tenant()
        location = self.generator.config.resource_location
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[resource_location]={location}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('resource_locations')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('resource_location'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_current_month_filter_subscription_guid(self):
        """Test execute_query for current month on monthly filtered by subscription_guid."""
        self.generator.add_data_to_tenant()
        guid = self.generator.config.subscription_guid
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[subscription_guid]={guid}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_service(self):
        """Test execute_query for current month on monthly filtered by service."""
        self.generator = OCPAzureReportDataGenerator(
            self.tenant, self.provider, current_month_only=True
        )
        self.generator.add_data_to_tenant(
            fixed_fields=[
                'subscription_guid',
                'resource_location',
                'tags',
                'service_name',
            ]
        )

        service = self.generator.config.service_name
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[service_name]={service}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()

        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))

        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        filters = {**self.this_month_filter, 'service_name__icontains': service}
        for filt in handler._mapper.report_type_map.get('filter'):
            if filt:
                qf = QueryFilter(**filt)
                filters.update({qf.composed_query_string(): qf.parameter})
        current_totals = self.get_totals_by_time_scope(aggregates, filters)
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_resource_location(self):
        """Test execute_query for current month on monthly filtered by resource_location."""
        self.generator.add_data_to_tenant()
        location = self.generator.config.resource_location
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[resource_location]={location}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    @patch('api.query_params.QueryParameters.accept_type', new_callable=PropertyMock)
    def test_execute_query_current_month_filter_resource_location_csv(
        self, mock_accept
    ):
        """Test execute_query on monthly filtered by resource_location for csv."""
        self.generator.add_data_to_tenant()
        mock_accept.return_value = 'text/csv'
        url = f'?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[resource_location]={self.generator.config.resource_location}'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        self.assertEqual(len(data), 1)
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            self.assertEqual(month_val, cmonth_str)

    @patch('api.query_params.QueryParameters.accept_type', new_callable=PropertyMock)
    def test_execute_query_curr_month_by_subscription_guid_w_limit_csv(
        self, mock_accept
    ):
        """Test execute_query for current month on monthly by subscription_guid with limt as csv."""
        mock_accept.return_value = 'text/csv'
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[limit]=2&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')

        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value', 0), current_totals.get('cost', 1))

        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        self.assertEqual(len(data), 2)
        for data_item in data:
            month = data_item.get('date', 'not-a-date')
            self.assertEqual(month, cmonth_str)

    def test_execute_query_w_delta(self):
        """Test grouped by deltas."""
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        path = reverse('reports-openshift-azure-costs')
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[subscription_guid]=*&delta=cost'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView, path)
        handler = OCPAzureReportQueryHandler(query_params)
        # test the calculations
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        subs = data[0].get('subscription_guids', [{}])
        for sub in subs:
            current_total = Decimal(0)
            prev_total = Decimal(0)

            # fetch the expected sums from the DB.
            with tenant_context(self.tenant):
                curr = OCPAzureCostLineItemDailySummary.objects.filter(
                    usage_start__date__gte=self.dh.this_month_start,
                    usage_start__date__lte=self.dh.today,
                    subscription_guid=sub.get('subscription_guid'),
                ).aggregate(value=Sum(F('pretax_cost') + F('markup_cost')))
                current_total = Decimal(curr.get('value'))

                prev = OCPAzureCostLineItemDailySummary.objects.filter(
                    usage_start__date__gte=self.dh.last_month_start,
                    usage_start__date__lte=self.dh.today - relativedelta(months=1),
                    subscription_guid=sub.get('subscription_guid'),
                ).aggregate(value=Sum(F('pretax_cost') + F('markup_cost')))
                prev_total = Decimal(prev.get('value', Decimal(0)))

            expected_delta_value = Decimal(current_total - prev_total)
            expected_delta_percent = Decimal(
                (current_total - prev_total) / prev_total * 100
            )

            values = sub.get('values', [{}])[0]
            self.assertIn('delta_value', values)
            self.assertIn('delta_percent', values)
            self.assertEqual(values.get('delta_value', 'str'), expected_delta_value)
            self.assertEqual(values.get('delta_percent', 'str'), expected_delta_percent)

        current_total = Decimal(0)
        prev_total = Decimal(0)

        # fetch the expected sums from the DB.
        with tenant_context(self.tenant):
            curr = OCPAzureCostLineItemDailySummary.objects.filter(
                usage_start__gte=self.dh.this_month_start,
                usage_start__lte=self.dh.today,
            ).aggregate(value=Sum(F('pretax_cost') + F('markup_cost')))
            current_total = Decimal(curr.get('value'))

            prev = OCPAzureCostLineItemDailySummary.objects.filter(
                usage_start__gte=self.dh.last_month_start,
                usage_start__lte=self.dh.today - relativedelta(months=1),
            ).aggregate(value=Sum(F('pretax_cost') + F('markup_cost')))
            prev_total = Decimal(prev.get('value'))

        expected_delta_value = Decimal(current_total - prev_total)
        expected_delta_percent = Decimal(
            (current_total - prev_total) / prev_total * 100
        )

        delta = query_output.get('delta')
        self.assertIsNotNone(delta.get('value'))
        self.assertIsNotNone(delta.get('percent'))
        self.assertEqual(delta.get('value', 'str'), expected_delta_value)
        self.assertEqual(delta.get('percent', 'str'), expected_delta_percent)

    def test_execute_query_w_delta_no_previous_data(self):
        """Test deltas with no previous data."""
        self.generator = OCPAzureReportDataGenerator(
            self.tenant, self.provider, current_month_only=True
        )
        self.generator.add_data_to_tenant()

        url = '?filter[time_scope_value]=-1&delta=cost'
        path = reverse('reports-openshift-azure-costs')
        query_params = self.mocked_query_params(url, OCPAzureCostView, path)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        total_cost = query_output.get('total', {}).get('cost', {}).get('value', 1)
        delta = query_output.get('delta')
        self.assertIsNotNone(delta.get('value'))
        self.assertIsNone(delta.get('percent', 0))
        self.assertEqual(delta.get('value', 0), total_cost)

    def test_execute_query_orderby_delta(self):
        """Test execute_query with ordering by delta ascending."""
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&order_by[delta]=asc&group_by[subscription_guid]=*&delta=cost'  # noqa: E501
        path = reverse('reports-openshift-azure-costs')
        query_params = self.mocked_query_params(url, OCPAzureCostView, path)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        cmonth_str = self.dh.this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date', 'not-a-date')
            month_data = data_item.get('subscription_guids')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('subscription_guid'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsInstance(
                    month_item.get('values')[0].get('delta_value'), Decimal
                )

    def test_calculate_total(self):
        """Test that calculated totals return correctly."""
        self.generator.add_data_to_tenant()
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly'
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        expected_units = 'USD'
        with tenant_context(self.tenant):
            result = handler.calculate_total(**{'cost_units': expected_units})

        aggregates = handler._mapper.report_type_map.get('aggregates')
        current_totals = self.get_totals_by_time_scope(
            aggregates, self.this_month_filter
        )
        self.assertEqual(
            result.get('cost', {}).get('value', 0), current_totals.get('cost', 1)
        )
        self.assertEqual(result.get('cost', {}).get('units', 'not-USD'), expected_units)

    def test_percent_delta(self):
        """Test _percent_delta() utility method."""
        url = '?'
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        self.assertEqual(handler._percent_delta(10, 5), 100)

    def test_rank_list_by_subscription_guid(self):
        """Test rank list limit with subscription_guid alias."""
        # No need to fill db
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[limit]=2&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        data_list = [
            {'subscription_guid': '1', 'total': 5, 'rank': 1},
            {'subscription_guid': '2', 'total': 4, 'rank': 2},
            {'subscription_guid': '3', 'total': 3, 'rank': 3},
            {'subscription_guid': '4', 'total': 2, 'rank': 4},
        ]
        expected = [
            {'subscription_guid': '1', 'total': 5, 'rank': 1},
            {'subscription_guid': '2', 'total': 4, 'rank': 2},
            {
                'subscription_guid': '2 Others',
                'cost': 0,
                'markup_cost': 0,
                'derived_cost': 0,
                'infrastructure_cost': 0,
                'total': 5,
                'rank': 3,
            },
        ]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_rank_list_by_service_name(self):
        """Test rank list limit with service_name grouping."""
        # No need to fill db
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[limit]=2&group_by[service_name]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        data_list = [
            {'service_name': '1', 'total': 5, 'rank': 1},
            {'service_name': '2', 'total': 4, 'rank': 2},
            {'service_name': '3', 'total': 3, 'rank': 3},
            {'service_name': '4', 'total': 2, 'rank': 4},
        ]
        expected = [
            {'service_name': '1', 'total': 5, 'rank': 1},
            {'service_name': '2', 'total': 4, 'rank': 2},
            {
                'cost': 0,
                'derived_cost': 0,
                'infrastructure_cost': 0,
                'markup_cost': 0,
                'service_name': '2 Others',
                'total': 5,
                'rank': 3,
            },
        ]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_rank_list_with_offset(self):
        """Test rank list limit and offset with subscription_guid alias."""
        # No need to fill db
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&filter[limit]=1&filter[offset]=1&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        data_list = [
            {'subscription_guid': '1', 'total': 5, 'rank': 1},
            {'subscription_guid': '2', 'total': 4, 'rank': 2},
            {'subscription_guid': '3', 'total': 3, 'rank': 3},
            {'subscription_guid': '4', 'total': 2, 'rank': 4},
        ]
        expected = [{'subscription_guid': '2', 'total': 4, 'rank': 2}]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_query_costs_with_totals(self):
        """Test execute_query() - costs with totals.

        Query for instance_types, validating that cost totals are present.

        """
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[subscription_guid]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        for data_item in data:
            subscription_guids = data_item.get('subscription_guids')
            for subscription_guid in subscription_guids:
                self.assertIsNotNone(subscription_guid.get('values'))
                self.assertGreater(len(subscription_guid.get('values')), 0)
                for value in subscription_guid.get('values'):
                    self.assertIsInstance(value.get('cost', {}).get('value'), Decimal)
                    self.assertGreater(value.get('cost', {}).get('value'), Decimal(0))

    def test_query_instance_types_with_totals(self):
        """Test execute_query() - instance types with totals.

        Query for instance_types, validating that cost totals are present.

        """
        self.generator.add_data_to_tenant()
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant()

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[instance_type]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureInstanceTypeView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        for data_item in data:
            instance_types = data_item.get('instance_types')
            for it in instance_types:
                self.assertIsNotNone(it.get('values'))
                self.assertGreater(len(it.get('values')), 0)
                for value in it.get('values'):
                    self.assertIsInstance(value.get('cost', {}).get('value'), Decimal)
                    self.assertGreaterEqual(
                        value.get('cost', {})
                        .get('value')
                        .quantize(Decimal('.0001'), ROUND_HALF_UP),
                        Decimal(0),
                    )
                    # FIXME: usage doesn't have units yet. waiting on MSFT
                    # self.assertIsInstance(value.get('usage', {}).get('value'), Decimal)
                    # self.assertGreater(value.get('usage', {}).get('value'), Decimal(0))
                    self.assertIsInstance(value.get('usage', {}), dict)
                    self.assertGreaterEqual(
                        value.get('usage', {})
                        .get('value', {})
                        .quantize(Decimal('.0001'), ROUND_HALF_UP),
                        Decimal(0),
                    )

    def test_query_storage_with_totals(self):
        """Test execute_query() - storage with totals.

        Query for storage, validating that cost totals are present.

        """
        self.generator.add_data_to_tenant(service_name='Storage')
        OCPAzureReportDataGenerator(self.tenant, self.provider).add_data_to_tenant(service_name='Storage')

        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly&group_by[service_name]=*'  # noqa: E501
        query_params = self.mocked_query_params(url, OCPAzureStorageView)
        handler = OCPAzureReportQueryHandler(query_params)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        for data_item in data:
            services = data_item.get('service_names')
            self.assertIsNotNone(services)
            for srv in services:
                self.assertIsNotNone(srv.get('values'))
                self.assertGreater(len(srv.get('values')), 0)
                for value in srv.get('values'):
                    self.assertIsInstance(value.get('cost', {}).get('value'), Decimal)
                    self.assertGreater(value.get('cost', {}).get('value'), Decimal(0))
                    # FIXME: usage doesn't have units yet. waiting on MSFT
                    # self.assertIsInstance(value.get('usage', {}).get('value'), Decimal)
                    # self.assertGreater(value.get('usage', {}).get('value'), Decimal(0))
                    self.assertIsInstance(value.get('usage', {}), dict)
                    self.assertGreater(
                        value.get('usage', {}).get('value', {}), Decimal(0)
                    )

    def test_order_by(self):
        """Test that order_by returns properly sorted data."""
        # Do not need to fill db
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly'
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)

        unordered_data = [
            {'date': self.dh.today, 'delta_percent': 8, 'total': 6.2, 'rank': 2},
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 1},
            {'date': self.dh.today, 'delta_percent': 7, 'total': 8.2, 'rank': 1},
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 2},
        ]

        order_fields = ['date', 'rank']
        expected = [
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 1},
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 2},
            {'date': self.dh.today, 'delta_percent': 7, 'total': 8.2, 'rank': 1},
            {'date': self.dh.today, 'delta_percent': 8, 'total': 6.2, 'rank': 2},
        ]

        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)

        order_fields = ['date', '-delta']
        expected = [
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 1},
            {'date': self.dh.yesterday, 'delta_percent': 4, 'total': 2.2, 'rank': 2},
            {'date': self.dh.today, 'delta_percent': 8, 'total': 6.2, 'rank': 2},
            {'date': self.dh.today, 'delta_percent': 7, 'total': 8.2, 'rank': 1},
        ]

        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)

    def test_order_by_null_values(self):
        """Test that order_by returns properly sorted data with null data."""
        # Do not need to fill db
        url = '?filter[time_scope_units]=month&filter[time_scope_value]=-1&filter[resolution]=monthly'
        query_params = self.mocked_query_params(url, OCPAzureCostView)
        handler = OCPAzureReportQueryHandler(query_params)

        unordered_data = [
            {'node': None, 'cluster': 'cluster-1'},
            {'node': 'alpha', 'cluster': 'cluster-2'},
            {'node': 'bravo', 'cluster': 'cluster-3'},
            {'node': 'oscar', 'cluster': 'cluster-4'},
        ]

        order_fields = ['node']
        expected = [
            {'node': 'alpha', 'cluster': 'cluster-2'},
            {'node': 'bravo', 'cluster': 'cluster-3'},
            {'node': 'no-node', 'cluster': 'cluster-1'},
            {'node': 'oscar', 'cluster': 'cluster-4'},
        ]
        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)
