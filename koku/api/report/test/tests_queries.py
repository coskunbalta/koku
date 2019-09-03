#
# Copyright 2018 Red Hat, Inc.
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
import copy
import random
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from urllib.parse import quote_plus

from django.db.models import Sum
from django.test import TestCase
from tenant_schemas.utils import tenant_context

from api.iam.test.iam_test_case import IamTestCase
from api.report.aws.query_handler import AWSReportQueryHandler
from api.report.ocp.query_handler import OCPReportQueryHandler
from api.report.queries import strip_tag_prefix
from api.report.test.aws.helpers import AWSReportDataGenerator
from api.report.test.ocp.helpers import OCPReportDataGenerator
from api.tags.aws.queries import AWSTagQueryHandler
from api.utils import DateHelper
from reporting.models import (AWSCostEntryLineItemDailySummary,
                              AWSCostEntryProduct)


class ReportQueryUtilsTest(TestCase):
    """Test the report query class functions."""

    def test_has_wildcard_yes(self):
        """Test a list has a wildcard."""
        result = AWSReportQueryHandler.has_wildcard(['abc', '*'])
        self.assertTrue(result)

    def test_has_wildcard_no(self):
        """Test a list doesn't have a wildcard."""
        result = AWSReportQueryHandler.has_wildcard(['abc', 'def'])
        self.assertFalse(result)

    def test_has_wildcard_none(self):
        """Test an empty list doesn't have a wildcard."""
        result = AWSReportQueryHandler.has_wildcard([])
        self.assertFalse(result)

    def test_group_data_by_list(self):
        """Test the _group_data_by_list method."""
        group_by = ['account', 'service']
        data = [{'account': 'a1', 'service': 's1', 'units': 'USD', 'total': 4},
                {'account': 'a1', 'service': 's2', 'units': 'USD', 'total': 5},
                {'account': 'a2', 'service': 's1', 'units': 'USD', 'total': 6},
                {'account': 'a2', 'service': 's2', 'units': 'USD', 'total': 5},
                {'account': 'a1', 'service': 's3', 'units': 'USD', 'total': 5}]
        out_data = AWSReportQueryHandler._group_data_by_list(group_by, 0, data)
        expected = {'a1':
                    {'s1': [{'account': 'a1', 'service': 's1', 'units': 'USD', 'total': 4}],
                     's2': [{'account': 'a1', 'service': 's2', 'units': 'USD', 'total': 5}],
                        's3': [
                        {'account': 'a1', 'service': 's3', 'units': 'USD', 'total': 5}]},
                    'a2':
                    {'s1': [{'account': 'a2', 'service': 's1', 'units': 'USD', 'total': 6}],
                        's2': [{'account': 'a2', 'service': 's2', 'units': 'USD', 'total': 5}]}}
        self.assertEqual(expected, out_data)

    def test_group_data_by_list_missing_units(self):
        """Test the _group_data_by_list method when duplicates occur due to missing units."""
        group_by = ['instance_type']
        data = [{'date': '2018-07-22', 'units': '', 'instance_type': 't2.micro', 'total': 30.0, 'count': 0},
                {'date': '2018-07-22', 'units': 'Hrs', 'instance_type': 't2.small', 'total': 17.0, 'count': 0},
                {'date': '2018-07-22', 'units': 'Hrs', 'instance_type': 't2.micro', 'total': 1.0, 'count': 0}]
        out_data = AWSReportQueryHandler._group_data_by_list(group_by, 0, data)
        expected = {'t2.micro': [
            {'date': '2018-07-22', 'units': 'Hrs', 'instance_type': 't2.micro', 'total': 1.0, 'count': 0},
            {'date': '2018-07-22', 'units': '', 'instance_type': 't2.micro', 'total': 30.0, 'count': 0}],
            't2.small': [
                {'date': '2018-07-22', 'units': 'Hrs', 'instance_type': 't2.small', 'total': 17.0, 'count': 0}]}
        self.assertEqual(expected, out_data)


class ReportQueryTest(IamTestCase):
    """Tests the report queries."""

    def setUp(self):
        """Set up the customer view tests."""
        super().setUp()
        self.fake_aws = AWSReportDataGenerator()

    def test_transform_null_group(self):
        """Test transform data with null group value."""
        handler = AWSReportQueryHandler({}, '', self.tenant,
                                        **{'report_type': 'costs'})
        groups = ['region']
        group_index = 0
        data = {None: [{'region': None, 'units': 'USD'}]}
        expected = [{'region': 'no-region', 'values': [{'region': 'no-region', 'units': 'USD'}]}]
        out_data = handler._transform_data(groups, group_index, data)
        self.assertEqual(expected, out_data)

        data = {'us-east': [{'region': 'us-east', 'units': 'USD'}]}
        expected = [{'region': 'us-east', 'values': [{'region': 'us-east', 'units': 'USD'}]}]
        out_data = handler._transform_data(groups, group_index, data)
        self.assertEqual(expected, out_data)

        data = {None: {'region': None, 'units': 'USD'}}
        expected = [{'region': 'no-region', 'values': {'region': None, 'units': 'USD'}}]
        out_data = handler._transform_data(groups, group_index, data)
        self.assertEqual(expected, out_data)

    def test_has_filter_no_filter(self):
        """Test the default filter query parameters."""
        handler = AWSReportQueryHandler({}, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertTrue(handler.check_query_params('filter', 'time_scope_units'))
        self.assertTrue(handler.check_query_params('filter', 'time_scope_value'))
        self.assertTrue(handler.check_query_params('filter', 'resolution'))
        self.assertEqual(handler.query_parameters.get('filter').get('time_scope_units'), 'day')
        self.assertEqual(handler.query_parameters.get('filter').get('time_scope_value'), '-10')
        self.assertEqual(handler.query_parameters.get('filter').get('resolution'), 'daily')

    def test_has_filter_with_filter(self):
        """Test the has_filter method with filter in the query params."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertIsNotNone(handler.check_query_params('filter', 'time_scope_value'))

    def test_get_group_by_no_data(self):
        """Test the get_group_by_data method with no data in the query params."""
        handler = AWSReportQueryHandler({}, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertFalse(handler.get_query_param_data('group_by', 'service'))

    def test_get_group_by_with_service_list(self):
        """Test the get_group_by_data method with no data in the query params."""
        expected = ['a', 'b']
        query_string = '?group_by[service]=a&group_by[service]=b'
        handler = AWSReportQueryHandler({'group_by':
                                        {'service': expected}},
                                        query_string,
                                        self.tenant,
                                        **{'report_type': 'costs'})
        service = handler.get_query_param_data('group_by', 'service')
        self.assertEqual(expected, service)

    def test_get_group_by_with_group_by_and_limit_params(self):
        """Test the _get_group_by method with limit and group by params."""
        expected = ['account']
        query_string = '?group_by[account]=*&filter[limit]=1'
        handler = AWSReportQueryHandler(
            {
                'group_by': {'account': ['*']},
                'filter': {'limit': 1}
            },
            query_string,
            self.tenant,
            **{'report_type': 'instance_type'}
        )
        group_by = handler._get_group_by()

        self.assertEqual(expected, group_by)

    def test_get_group_by_with_group_by_and_no_limit_params(self):
        """Test the _get_group_by method with group by params."""
        expected = ['account', 'instance_type']
        query_string = '?group_by[account]=*'
        handler = AWSReportQueryHandler(
            {
                'group_by': {'account': ['*']},
            },
            query_string,
            self.tenant,
            **{'report_type': 'instance_type'}
        )
        group_by = handler._get_group_by()

        self.assertEqual(expected, group_by)

    def test_get_group_by_with_limit_and_no_group_by_params(self):
        """Test the _get_group_by method with limit params."""
        expected = ['instance_type']
        query_string = '?group_by[account]=*'
        handler = AWSReportQueryHandler(
            {
                'filter': {'limit': 1},
            },
            query_string,
            self.tenant,
            **{'report_type': 'instance_type'}
        )
        group_by = handler._get_group_by()

        self.assertEqual(expected, group_by)

    def test_get_resolution_empty_default(self):
        """Test get_resolution returns default when query params are empty."""
        query_params = {}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.resolution, 'daily')

    def test_get_resolution_empty_day_time_scope(self):
        """Test get_resolution returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -10}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_resolution(), 'daily')

    def test_get_time_scope_units_empty_default(self):
        """Test get_time_scope_units returns default when query params are empty."""
        query_params = {}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_units(), 'day')
        self.assertEqual(handler.get_time_scope_units(), 'day')

    def test_get_time_scope_units_empty_month_time_scope(self):
        """Test get_time_scope_units returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -1}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_units(), 'month')

    def test_get_time_scope_units_empty_day_time_scope(self):
        """Test get_time_scope_units returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_value': -10}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_units(), 'day')

    def test_get_time_scope_value_empty_default(self):
        """Test get_time_scope_value returns default when query params are empty."""
        query_params = {}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_value(), -10)
        self.assertEqual(handler.get_time_scope_value(), -10)

    def test_get_time_scope_value_empty_month_time_scope(self):
        """Test get_time_scope_value returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_units': 'month'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_value(), -1)

    def test_get_time_scope_value_empty_day_time_scope(self):
        """Test get_time_scope_value returns default when time_scope is month."""
        query_params = {'filter': {'time_scope_units': 'day'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        self.assertEqual(handler.get_time_scope_value(), -10)

    def test_get_time_frame_filter_current_month(self):
        """Test _get_time_frame_filter for current month."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, DateHelper().this_month_start)
        self.assertEqual(end.date(), DateHelper().today.date())
        self.assertIsInstance(interval, list)
        self.assertEqual(len(interval), DateHelper().today.day)

    def test_get_time_frame_filter_previous_month(self):
        """Test _get_time_frame_filter for previous month."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -2,
                         'time_scope_units': 'month'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        start = handler.start_datetime
        end = handler.end_datetime
        interval = handler.time_interval
        self.assertEqual(start, DateHelper().last_month_start)
        self.assertEqual(end, DateHelper().last_month_end)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) >= 28)

    def test_get_time_frame_filter_last_ten(self):
        """Test _get_time_frame_filter for last ten days."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -10,
                         'time_scope_units': 'day'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        dh = DateHelper()
        nine_days_ago = dh.n_days_ago(dh.today, 9)
        start = handler.start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        end = handler.end_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        interval = handler.time_interval
        self.assertEqual(start, nine_days_ago)
        self.assertEqual(end, dh.today)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) == 10)

    def test_get_time_frame_filter_last_thirty(self):
        """Test _get_time_frame_filter for last thirty days."""
        query_params = {'filter':
                        {'resolution': 'daily',
                         'time_scope_value': -30,
                         'time_scope_units': 'day'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        dh = DateHelper()
        twenty_nine_days_ago = dh.n_days_ago(dh.today, 29)
        start = handler.start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        end = handler.end_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
        interval = handler.time_interval
        self.assertEqual(start, twenty_nine_days_ago)
        self.assertEqual(end, dh.today)
        self.assertIsInstance(interval, list)
        self.assertTrue(len(interval) == 30)

    def test_execute_take_defaults(self):
        """Test execute_query for current month on daily breakdown."""
        query_params = {}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))

    def test_execute_query_current_month_daily(self):
        """Test execute_query for current month on daily breakdown."""
        query_params = {'filter':
                        {'resolution': 'daily', 'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

    def test_execute_query_current_month_monthly(self):
        """Test execute_query for current month on monthly breakdown."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'}}
        handler = AWSReportQueryHandler(query_params, '', self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        self.assertIsNotNone(query_output.get('data'))
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

    def test_execute_query_current_month_by_service(self):
        """Test execute_query for current month on monthly breakdown by service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'service': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[service]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('services')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                compute = month_item.get('service')
                self.assertEqual(compute, 'AmazonEC2')
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_by_filtered_service(self):
        """Test execute_query monthly breakdown by filtered service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'service': ['AmazonEC2']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[service]=AmazonEC2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('services')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                compute = month_item.get('service')
                self.assertEqual(compute, 'AmazonEC2')
                self.assertIsInstance(month_item.get('values'), list)

    def test_query_by_partial_filtered_service(self):
        """Test execute_query monthly breakdown by filtered service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'service': ['eC2']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[service]=eC2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('services')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                compute = month_item.get('service')
                self.assertEqual(compute, 'AmazonEC2')
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_current_month_by_account(self):
        """Test execute_query for current month on monthly breakdown by account."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                account = month_item.get('account')
                self.assertEqual(account, self.fake_aws.account_id)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_by_account_by_service(self):
        """Test execute_query for current month breakdown by account by service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*'],
                                     'service': ['*']}}
        query_string = '?group_by[account]=*&group_by[service]=*'
        handler = AWSReportQueryHandler(query_params, query_string,
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                account = month_item.get('account')
                self.assertEqual(account, self.fake_aws.account_id)
                self.assertIsInstance(month_item.get('services'), list)

    def test_execute_query_with_counts(self):
        """Test execute_query for with counts of unique resources."""
        with tenant_context(self.tenant):
            instance_type = AWSCostEntryProduct.objects.first().instance_type

        query_params = {'filter': {'resolution': 'monthly',
                                   'time_scope_value': -1,
                                   'time_scope_units': 'month'}}
        query_string = '?filter[time_scope_value]=-1&filter[resolution]=monthly'
        extras = {'report_type': 'instance_type',
                  'group_by': ['instance_type']}
        handler = AWSReportQueryHandler(query_params, query_string,
                                        self.tenant,
                                        **extras)
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))

        total = query_output.get('total')
        self.assertIsNotNone(total.get('count'))
        self.assertEqual(total.get('count', {}).get('value'), 24)

        for data_item in data:
            instance_types = data_item.get('instance_types')
            for it in instance_types:
                if it['instance_type'] == instance_type:
                    actual_count = it['values'][0].get('count', {}).get('value')
                    self.assertEqual(actual_count, 1)

    def test_execute_query_curr_month_by_account_w_limit(self):
        """Test execute_query for current month on monthly breakdown by account with limit."""
        for _ in range(3):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator())

        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month', 'limit': 2},
                        'group_by': {'account': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*&filter[limit]=2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(3, len(month_data))
            for month_item in month_data:
                self.assertIsInstance(month_item.get('account'), str)
                self.assertIsInstance(month_item.get('values'), list)

    def test_execute_query_curr_month_by_account_w_order(self):
        """Test execute_query for current month on monthly breakdown by account with asc order."""
        for _ in range(3):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator())

        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']},
                        'order_by': {'cost': 'asc'}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(len(month_data), 4)
            current_total = 0
            for month_item in month_data:
                self.assertIsInstance(month_item.get('account'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost', {}).get('value'))
                data_point_total = month_item.get('values')[0].get('cost', {}).get('value')
                self.assertLess(current_total, data_point_total)
                current_total = data_point_total

    def test_execute_query_curr_month_by_account_w_order_by_account(self):
        """Test execute_query for current month on monthly breakdown by account with asc order."""
        for _ in range(3):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator())

        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']},
                        'order_by': {'account': 'asc'}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(len(month_data), 4)
            current = '0'
            for month_item in month_data:
                self.assertIsInstance(month_item.get('account'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('account'))
                data_point = month_item.get('values')[0].get('account')
                self.assertLess(current, data_point)
                current = data_point

    def test_execute_query_curr_month_by_region(self):
        """Test execute_query for current month on monthly breakdown by region."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'region': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[region]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('regions')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(1, len(month_data))
            for month_item in month_data:
                self.assertIsInstance(month_item.get('region'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_curr_month_by_filtered_region(self):
        """Test execute_query for current month on monthly breakdown by filtered region."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'region': [self.fake_aws.region]}}
        handler = AWSReportQueryHandler(query_params,
                                        f'?group_by[region]={self.fake_aws.region}',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertGreater(total.get('cost', {}).get('value'), 0)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('regions')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('region'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_curr_month_by_avail_zone(self):
        """Test execute_query for current month on monthly breakdown by avail_zone."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'az': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[az]=*',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('azs')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(len(month_data), 1)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('az'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_curr_month_by_filtered_avail_zone(self):
        """Test execute_query for current month on monthly breakdown by filtered avail_zone."""
        zone = self.fake_aws.availability_zone
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'az': [zone]}}
        handler = AWSReportQueryHandler(query_params,
                                        f'?group_by[az]={zone}',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()

        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('azs')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            self.assertEqual(1, len(month_data))
            for month_item in month_data:
                self.assertIsInstance(month_item.get('az'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNotNone(month_item.get('values')[0].get('cost'))

    def test_execute_query_current_month_filter_account(self):
        """Test execute_query for current month on monthly filtered by account."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'account': [self.fake_aws.account_alias]}}
        handler = AWSReportQueryHandler(query_params, '',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_service(self):
        """Test execute_query for current month on monthly filtered by service."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'service': ['AmazonEC2']}}
        handler = AWSReportQueryHandler(query_params, '',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()

        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))

        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_region(self):
        """Test execute_query for current month on monthly filtered by region."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'region': [self.fake_aws.region]}}
        handler = AWSReportQueryHandler(query_params, '',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertGreater(total.get('cost', {}).get('value'), 0)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_avail_zone(self):
        """Test execute_query for current month on monthly filtered by avail_zone."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'az': [self.fake_aws.availability_zone]}}
        handler = AWSReportQueryHandler(query_params, '',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('values')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)

    def test_execute_query_current_month_filter_avail_zone_csv(self):
        """Test execute_query for current month on monthly filtered by avail_zone for csv."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'az': [self.fake_aws.availability_zone]}}
        handler = AWSReportQueryHandler(query_params, '',
                                        self.tenant,
                                        **{'accept_type': 'text/csv',
                                            'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        self.assertEqual(len(data), 1)
        for data_item in data:
            month_val = data_item.get('date')
            self.assertEqual(month_val, cmonth_str)

    def test_execute_query_curr_month_by_account_w_limit_csv(self):
        """Test execute_query for current month on monthly by account with limt as csv."""
        for _ in range(5):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator())

        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month', 'limit': 2},
                        'group_by': {'account': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*&filter[limit]=2',
                                        self.tenant,
                                        **{'accept_type': 'text/csv',
                                           'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')

        self.assertIsNotNone(data)
        self.assertIsNotNone(query_output.get('total'))
        total = query_output.get('total')
        self.assertIsNotNone(total.get('cost'))
        self.assertEqual(total.get('cost', {}).get('value'), self.fake_aws.current_month_total)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        self.assertEqual(len(data[0].get('accounts')), 3)
        for data_item in data:
            month = data_item.get('date')
            self.assertEqual(month, cmonth_str)

    def test_execute_query_w_delta(self):
        """Test grouped by deltas."""
        dh = DateHelper()
        current_total = Decimal(0)
        prev_total = Decimal(0)

        previous_data = copy.deepcopy(self.fake_aws)
        previous_data.billing_period_end = dh.last_month_end
        previous_data.billing_period_start = dh.last_month_start
        previous_data.usage_end = dh.last_month_start + dh.one_day
        previous_data.usage_start = dh.last_month_start

        for _ in range(0, 3):
            # add some current data.
            self.fake_aws.add_data_to_tenant(self.fake_aws)
            # add some previous data.
            self.fake_aws.add_data_to_tenant(previous_data)

        # fetch the expected sums from the DB.
        with tenant_context(self.tenant):
            curr = AWSCostEntryLineItemDailySummary.objects.filter(
                usage_start__gte=dh.this_month_start,
                usage_end__lte=dh.this_month_end).aggregate(value=Sum('unblended_cost'))
            current_total = Decimal(curr.get('value'))

            prev = AWSCostEntryLineItemDailySummary.objects.filter(
                usage_start__gte=dh.last_month_start,
                usage_end__lte=dh.last_month_end).aggregate(value=Sum('unblended_cost'))
            prev_total = Decimal(prev.get('value'))

        expected_delta_value = Decimal(current_total - prev_total)
        expected_delta_percent = Decimal(
            (current_total - prev_total) / prev_total * 100
        )

        query_params = {'filter':
                        {'resolution': 'monthly',
                         'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']},
                        'delta': 'cost'}

        handler = AWSReportQueryHandler(query_params,
                                        '?group_by[account]=*&delta=True',
                                        self.tenant,
                                        **{'report_type': 'costs'})

        # test the calculations
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        values = data[0].get('accounts', [])[0].get('values', [])[0]
        self.assertIn('delta_value', values)
        self.assertIn('delta_percent', values)
        self.assertEqual(values.get('delta_value'), expected_delta_value)
        self.assertEqual(values.get('delta_percent'), expected_delta_percent)

        delta = query_output.get('delta')
        self.assertIsNotNone(delta.get('value'))
        self.assertIsNotNone(delta.get('percent'))
        self.assertEqual(delta.get('value'), expected_delta_value)
        self.assertEqual(delta.get('percent'), expected_delta_percent)

    def test_execute_query_w_delta_no_previous_data(self):
        """Test deltas with no previous data."""
        expected_delta_value = Decimal(self.fake_aws.current_month_total)
        expected_delta_percent = None

        query_params = {
            'filter': {'time_scope_value': -1},
            'delta': 'cost'
        }

        handler = AWSReportQueryHandler(query_params,
                                        '?filter[time_scope_value]=-10&delta=total',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        delta = query_output.get('delta')
        self.assertIsNotNone(delta.get('value'))
        self.assertIsNone(delta.get('percent'))
        self.assertEqual(delta.get('value'), expected_delta_value)
        self.assertEqual(delta.get('percent'), expected_delta_percent)

    def test_execute_query_orderby_delta(self):
        """Test execute_query with ordering by delta ascending."""
        dh = DateHelper()
        current_data = AWSReportDataGenerator()
        previous_data = copy.deepcopy(current_data)
        previous_data.billing_period_end = dh.last_month_end
        previous_data.billing_period_start = dh.last_month_start
        previous_data.usage_end = dh.last_month_start + timedelta(days=1)
        previous_data.usage_start = dh.last_month_start + timedelta(days=1)

        for _ in range(3):
            for _ in range(3):
                # add some current data.
                self.fake_aws.add_data_to_tenant(self.fake_aws)
                # add some past data.
                self.fake_aws.add_data_to_tenant(previous_data)

            # create another account id for the next loop
            current_data = AWSReportDataGenerator()
            previous_data = copy.deepcopy(current_data)
            previous_data.billing_period_end = dh.last_month_end
            previous_data.billing_period_start = dh.last_month_start
            previous_data.usage_end = dh.last_month_start + timedelta(days=1)
            previous_data.usage_start = dh.last_month_start + timedelta(days=1)

        query_params = {'filter':
                        {'resolution': 'monthly',
                         'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'order_by': {'delta': 'asc'},
                        'group_by': {'account': ['*']},
                        'delta': 'cost'}
        handler = AWSReportQueryHandler(query_params,
                                        '?group_by[account]=*&order_by[delta]=asc&delta=True',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        cmonth_str = DateHelper().this_month_start.strftime('%Y-%m')
        for data_item in data:
            month_val = data_item.get('date')
            month_data = data_item.get('accounts')
            self.assertEqual(month_val, cmonth_str)
            self.assertIsInstance(month_data, list)
            for month_item in month_data:
                self.assertIsInstance(month_item.get('account'), str)
                self.assertIsInstance(month_item.get('values'), list)
                self.assertIsNone(month_item.get('values')[0].get('delta_percent'))

    def test_execute_query_with_account_alias(self):
        """Test execute_query when account alias is avaiable."""
        query_params = {'filter':
                        {'resolution': 'monthly',
                         'time_scope_value': -1,
                         'time_scope_units': 'month',
                         'limit': 2},
                        'group_by': {'account': ['*']}}
        handler = AWSReportQueryHandler(query_params,
                                        '?group_by[account]=*&filter[limit]=2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')

        account_alias = data[0].get('accounts')[0].get('values')[0].get('account_alias')
        self.assertEqual(account_alias, self.fake_aws.account_alias)

    def test_execute_query_orderby_alias(self):
        """Test execute_query when account alias is avaiable."""
        # generate test data
        expected = {self.fake_aws.account_alias: self.fake_aws.account_id}
        for _ in range(0, 3):
            fake_data = AWSReportDataGenerator()
            expected[fake_data.account_alias] = fake_data.account_id
            self.fake_aws.add_data_to_tenant(fake_data)
        expected = OrderedDict(sorted(expected.items()))

        # execute query
        query_params = {'filter':
                        {'resolution': 'monthly',
                         'time_scope_value': -1,
                         'time_scope_units': 'month'},
                        'group_by': {'account': ['*']},
                        'order_by': {'account_alias': 'asc'}}
        handler = AWSReportQueryHandler(query_params,
                                        '?group_by[account]=[*]&order_by[account_alias]=asc',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')

        # test query output
        actual = OrderedDict()
        for datum in data:
            for account in datum.get('accounts'):
                for value in account.get('values'):
                    actual[value.get('account_alias')] = value.get('account')

        self.assertEqual(actual, expected)

    def test_calculate_total(self):
        """Test that calculated totals return correctly."""
        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month'
            }
        }
        handler = AWSReportQueryHandler(
            query_params,
            '',
            self.tenant,
            **{'report_type': 'costs'}
        )
        expected_units = 'USD'
        with tenant_context(self.tenant):
            result = handler.calculate_total(**{'cost_units': expected_units})

        self.assertEqual(result.get('cost', {}).get('value'), self.fake_aws.current_month_total)
        self.assertEqual(result.get('cost', {}).get('units'), expected_units)

    def test_percent_delta(self):
        """Test _percent_delta() utility method."""
        args = [{}, '', self.tenant]
        rqh = AWSReportQueryHandler(*args, **{'report_type': 'costs'})
        self.assertEqual(rqh._percent_delta(10, 5), 100)

    def test_rank_list(self):
        """Test rank list limit with account alias."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month', 'limit': 2},
                        'group_by': {'account': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*&filter[limit]=2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        data_list = [
            {'account': '1', 'account_alias': '1', 'total': 5, 'rank': 1},
            {'account': '2', 'account_alias': '2', 'total': 4, 'rank': 2},
            {'account': '3', 'account_alias': '3', 'total': 3, 'rank': 3},
            {'account': '4', 'account_alias': '4', 'total': 2, 'rank': 4}
        ]
        expected = [
            {'account': '1', 'account_alias': '1', 'total': 5, 'rank': 1},
            {'account': '2', 'account_alias': '2', 'total': 4, 'rank': 2},
            {'account': '2 Others', 'account_alias': '2 Others', 'cost': 0,
             'derived_cost': 0, 'infrastructure_cost': 0, 'total': 5, 'rank': 3}
        ]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_rank_list_no_account(self):
        """Test rank list limit with out account alias."""
        query_params = {'filter':
                        {'resolution': 'monthly', 'time_scope_value': -1,
                         'time_scope_units': 'month', 'limit': 2},
                        'group_by': {'service': ['*']}}
        handler = AWSReportQueryHandler(query_params, '?group_by[service]=*&filter[limit]=2',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        data_list = [
            {'service': '1', 'total': 5, 'rank': 1},
            {'service': '2', 'total': 4, 'rank': 2},
            {'service': '3', 'total': 3, 'rank': 3},
            {'service': '4', 'total': 2, 'rank': 4}
        ]
        expected = [
            {'service': '1', 'total': 5, 'rank': 1},
            {'service': '2', 'total': 4, 'rank': 2},
            {'cost': 0, 'derived_cost': 0, 'infrastructure_cost': 0,
             'service': '2 Others', 'total': 5, 'rank': 3}
        ]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_rank_list_with_offset(self):
        """Test rank list limit and offset with account alias."""
        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month',
                'limit': 1,
                'offset': 1
            },
            'group_by': {'account': ['*']}
        }
        handler = AWSReportQueryHandler(query_params, '?group_by[account]=*&filter[limit]=2&filter[offset]=1',
                                        self.tenant,
                                        **{'report_type': 'costs'})
        data_list = [
            {'account': '1', 'account_alias': '1', 'total': 5, 'rank': 1},
            {'account': '2', 'account_alias': '2', 'total': 4, 'rank': 2},
            {'account': '3', 'account_alias': '3', 'total': 3, 'rank': 3},
            {'account': '4', 'account_alias': '4', 'total': 2, 'rank': 4}
        ]
        expected = [
            {'account': '2', 'account_alias': '2', 'total': 4, 'rank': 2},
        ]
        ranked_list = handler._ranked_list(data_list)
        self.assertEqual(ranked_list, expected)

    def test_query_costs_with_totals(self):
        """Test execute_query() - costs with totals.

        Query for instance_types, validating that cost totals are present.

        """
        for _ in range(0, random.randint(3, 5)):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator(), product='ec2')
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator(), product='ebs')

        query_params = {'filter': {'resolution': 'monthly',
                                   'time_scope_value': -1,
                                   'time_scope_units': 'month'},
                        'group_by': {'account': ['*']}}
        query_string = '?filter[resolution]=monthly&' + \
                       'filter[time_scope_value]=-1&' + \
                       'filter[time_scope_units]=month&' + \
                       'group_by[account]=*'
        handler = AWSReportQueryHandler(query_params, query_string, self.tenant,
                                        **{'report_type': 'costs'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        for data_item in data:
            accounts = data_item.get('accounts')
            for account in accounts:
                self.assertIsNotNone(account.get('values'))
                self.assertGreater(len(account.get('values')), 0)
                for value in account.get('values'):
                    self.assertIsInstance(value.get('cost', {}).get('value'), Decimal)
                    self.assertGreater(value.get('cost', {}).get('value'), Decimal(0))

    def test_query_instance_types_with_totals(self):
        """Test execute_query() - instance types with totals.

        Query for instance_types, validating that cost totals are present.

        """
        for _ in range(0, random.randint(3, 5)):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator(), product='ec2')

        query_params = {'filter': {'resolution': 'monthly',
                                   'time_scope_value': -1,
                                   'time_scope_units': 'month'}}
        query_string = '?filter[resolution]=monthly&' + \
                       'filter[time_scope_value]=-1&' + \
                       'filter[time_scope_units]=month'
        handler = AWSReportQueryHandler(query_params, query_string, self.tenant,
                                        **{'report_type': 'instance_type',
                                           'group_by': ['instance_type']})
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
                    self.assertGreater(value.get('cost', {}).get('value'), Decimal(0))
                    self.assertIsInstance(value.get('usage', {}).get('value'), Decimal)
                    self.assertGreater(value.get('usage', {}).get('value'), Decimal(0))

    def test_query_storage_with_totals(self):
        """Test execute_query() - storage with totals.

        Query for storage, validating that cost totals are present.

        """
        for _ in range(0, random.randint(3, 5)):
            self.fake_aws.add_data_to_tenant(AWSReportDataGenerator(), product='ebs')

        query_params = {'filter': {'resolution': 'monthly',
                                   'time_scope_value': -1,
                                   'time_scope_units': 'month'},
                        'group_by': {'service': ['*']}}
        query_string = '?filter[resolution]=monthly&' + \
                       'filter[time_scope_value]=-1&' + \
                       'filter[time_scope_units]=month&' +  \
                       'group_by[service]=*'
        handler = AWSReportQueryHandler(query_params, query_string, self.tenant,
                                        **{'report_type': 'storage'})
        query_output = handler.execute_query()
        data = query_output.get('data')
        self.assertIsNotNone(data)

        for data_item in data:
            services = data_item.get('services')
            self.assertIsNotNone(services)
            for srv in services:
                # EBS is filed under the 'AmazonEC2' service.
                if srv.get('service') == 'AmazonEC2':
                    self.assertIsNotNone(srv.get('values'))
                    self.assertGreater(len(srv.get('values')), 0)
                    for value in srv.get('values'):
                        self.assertIsInstance(value.get('cost', {}).get('value'), Decimal)
                        self.assertGreater(value.get('cost', {}).get('value'), Decimal(0))
                        self.assertIsInstance(value.get('usage', {}).get('value'), Decimal)
                        self.assertGreater(value.get('usage', {}).get('value'), Decimal(0))

    def test_order_by(self):
        """Test that order_by returns properly sorted data."""
        today = datetime.utcnow()
        yesterday = today - timedelta(days=1)
        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month'
            }
        }
        handler = AWSReportQueryHandler(
            query_params,
            '',
            self.tenant,
            **{'report_type': 'costs'}
        )

        unordered_data = [
            {
                'date': today,
                'delta_percent': 8,
                'total': 6.2,
                'rank': 2
            },
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 1
            },
            {
                'date': today,
                'delta_percent': 7,
                'total': 8.2,
                'rank': 1
            },
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 2
            },
        ]

        order_fields = ['date', 'rank']
        expected = [
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 1
            },
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 2
            },
            {
                'date': today,
                'delta_percent': 7,
                'total': 8.2,
                'rank': 1
            },
            {
                'date': today,
                'delta_percent': 8,
                'total': 6.2,
                'rank': 2
            },

        ]

        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)

        order_fields = ['date', '-delta']
        expected = [
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 1
            },
            {
                'date': yesterday,
                'delta_percent': 4,
                'total': 2.2,
                'rank': 2
            },
            {
                'date': today,
                'delta_percent': 8,
                'total': 6.2,
                'rank': 2
            },
            {
                'date': today,
                'delta_percent': 7,
                'total': 8.2,
                'rank': 1
            },
        ]

        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)

    def test_order_by_null_values(self):
        """Test that order_by returns properly sorted data with null data."""
        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month'
            }
        }
        handler = OCPReportQueryHandler(
            query_params,
            '',
            self.tenant,
            **{'report_type': 'costs'}
        )

        unordered_data = [
            {
                'node': None,
                'cluster': 'cluster-1'
            },
            {
                'node': 'alpha',
                'cluster': 'cluster-2'
            },
            {
                'node': 'bravo',
                'cluster': 'cluster-3'
            },
            {
                'node': 'oscar',
                'cluster': 'cluster-4'
            },
        ]

        order_fields = ['node']
        expected = [
            {
                'node': 'alpha',
                'cluster': 'cluster-2'
            },
            {
                'node': 'bravo',
                'cluster': 'cluster-3'
            },
            {
                'node': 'no-node',
                'cluster': 'cluster-1'
            },
            {
                'node': 'oscar',
                'cluster': 'cluster-4'
            },

        ]
        ordered_data = handler.order_by(unordered_data, order_fields)
        self.assertEqual(ordered_data, expected)

    def test_strip_tag_prefix(self):
        """Verify that our tag prefix is stripped from a string."""
        tag_str = 'tag:project'

        result = strip_tag_prefix(tag_str)

        self.assertEqual(result, tag_str.replace('tag:', ''))

    def test_execute_query_with_tag_filter(self):
        """Test that data is filtered by tag key."""
        handler = AWSTagQueryHandler('', {}, self.tenant)
        tag_keys = handler.get_tag_keys(filters=False)
        filter_key = tag_keys[0]
        tag_keys = ['tag:' + tag for tag in tag_keys]

        with tenant_context(self.tenant):
            labels = AWSCostEntryLineItemDailySummary.objects\
                .filter(usage_start__gte=self.fake_aws.dh.this_month_start)\
                .filter(tags__has_key=filter_key)\
                .values(*['tags'])\
                .all()
            label_of_interest = labels[0]
            filter_value = label_of_interest.get('tags', {}).get(filter_key)

            totals = AWSCostEntryLineItemDailySummary.objects\
                .filter(usage_start__gte=self.fake_aws.dh.this_month_start)\
                .filter(**{f'tags__{filter_key}': filter_value})\
                .aggregate(**{'cost': Sum('unblended_cost')})

        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month',
                f'tag:{filter_key}': [filter_value]
            }
        }
        query_string = f'?filter[tag:{filter_key}]={filter_value}'

        handler = AWSReportQueryHandler(
            query_params,
            query_string,
            self.tenant,
            **{'report_type': 'costs', 'tag_keys': tag_keys}
        )

        data = handler.execute_query()
        data_totals = data.get('total', {})
        for key in totals:
            result = data_totals.get(key, {}).get('value')
            self.assertEqual(result, totals[key])

    def test_execute_query_with_wildcard_tag_filter(self):
        """Test that data is filtered to include entries with tag key."""
        handler = AWSTagQueryHandler('', {}, self.tenant)
        tag_keys = handler.get_tag_keys(filters=False)
        filter_key = tag_keys[0]
        tag_keys = ['tag:' + tag for tag in tag_keys]

        with tenant_context(self.tenant):
            totals = AWSCostEntryLineItemDailySummary.objects\
                .filter(usage_start__gte=self.dh.this_month_start)\
                .filter(**{'tags__has_key': filter_key})\
                .aggregate(
                    **{'cost': Sum('unblended_cost')})

        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month',
                f'tag:{filter_key}': ['*']
            }
        }
        query_string = f'?filter[tag:{filter_key}]=*'

        handler = AWSReportQueryHandler(
            query_params,
            query_string,
            self.tenant,
            **{'report_type': 'costs', 'tag_keys': tag_keys}
        )

        data = handler.execute_query()
        data_totals = data.get('total', {})
        for key in totals:
            result = data_totals.get(key, {}).get('value')
            self.assertEqual(result, totals[key])

    def test_execute_query_with_tag_group_by(self):
        """Test that data is grouped by tag key."""
        handler = AWSTagQueryHandler('', {}, self.tenant)
        tag_keys = handler.get_tag_keys(filters=False)
        group_by_key = tag_keys[0]
        tag_keys = ['tag:' + tag for tag in tag_keys]

        with tenant_context(self.tenant):
            totals = AWSCostEntryLineItemDailySummary.objects\
                .filter(usage_start__gte=self.fake_aws.dh.this_month_start)\
                .filter(**{'tags__has_key': group_by_key})\
                .aggregate(
                    **{'cost': Sum('unblended_cost')})

        query_params = {
            'filter': {
                'resolution': 'monthly',
                'time_scope_value': -1,
                'time_scope_units': 'month',
            },
            'group_by': {
                f'tag:{group_by_key}': ['*']
            }
        }
        query_string = quote_plus(f'?group_by[tag:{group_by_key}]=*')

        handler = AWSReportQueryHandler(
            query_params,
            query_string,
            self.tenant,
            **{'report_type': 'costs', 'tag_keys': tag_keys}
        )

        data = handler.execute_query()
        data_totals = data.get('total', {})
        data = data.get('data', [])
        expected_keys = ['date', group_by_key + 's']
        for entry in data:
            self.assertEqual(list(entry.keys()), expected_keys)
        for key in totals:
            result = data_totals.get(key, {}).get('value')
            self.assertEqual(result, totals[key])

    def test_ocp_cpu_query_group_by_cluster(self):
        """Test that group by cluster includes cluster and cluster_alias."""
        for _ in range(1, 5):
            OCPReportDataGenerator(self.tenant).add_data_to_tenant()

        query_params = {'filter': {'resolution': 'monthly',
                                   'time_scope_value': -1,
                                   'time_scope_units': 'month',
                                   'limit': 3},
                        'group_by': {'cluster': ['*']}}
        query_string = '?filter[resolution]=monthly&' + \
                       'filter[time_scope_value]=-1&' + \
                       'filter[time_scope_units]=month&' + \
                       'filter[limit]=3&' + \
                       'group_by[cluster]=*'

        handler = OCPReportQueryHandler(
            query_params,
            query_string,
            self.tenant,
            **{'report_type': 'cpu'}
        )

        query_data = handler.execute_query()
        for data in query_data.get('data'):
            self.assertIn('clusters', data)
            for cluster_data in data.get('clusters'):
                self.assertIn('cluster', cluster_data)
                self.assertIn('values', cluster_data)
                for cluster_value in cluster_data.get('values'):
                    self.assertIn('cluster', cluster_value)
                    self.assertIn('cluster_alias', cluster_value)
                    self.assertIsNotNone('cluster', cluster_value)
                    self.assertIsNotNone('cluster_alias', cluster_value)
