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
"""AWS Query Handling for Reports."""
import copy
import logging

from django.db.models import (F, Value, Window)
from django.db.models.expressions import Func
from django.db.models.functions import Coalesce, Concat, RowNumber
from tenant_schemas.utils import tenant_context

from api.models import Provider
from api.report.aws.provider_map import AWSProviderMap
from api.report.queries import ReportQueryHandler

LOG = logging.getLogger(__name__)

EXPORT_COLUMNS = ['cost_entry_id', 'cost_entry_bill_id',
                  'cost_entry_product_id', 'cost_entry_pricing_id',
                  'cost_entry_reservation_id', 'tags',
                  'invoice_id', 'line_item_type', 'usage_account_id',
                  'usage_start', 'usage_end', 'product_code',
                  'usage_type', 'operation', 'availability_zone',
                  'usage_amount', 'normalization_factor',
                  'normalized_usage_amount', 'currency_code',
                  'unblended_rate', 'unblended_cost', 'blended_rate',
                  'blended_cost', 'tax_type']


class AWSReportQueryHandler(ReportQueryHandler):
    """Handles report queries and responses for AWS."""

    provider = Provider.PROVIDER_AWS

    def __init__(self, parameters):
        """Establish AWS report query handler.

        Args:
            parameters    (QueryParameters): parameter object for query

        """
        # do not override mapper if its already set
        try:
            getattr(self, '_mapper')
        except AttributeError:
            self._mapper = AWSProviderMap(provider=self.provider,
                                          report_type=parameters.report_type)

        self.group_by_options = self._mapper.provider_map.get('group_by_options')
        self._limit = parameters.get_filter('limit')

        # super() needs to be called after _mapper and _limit is set
        super().__init__(parameters)

    @property
    def annotations(self):
        """Create dictionary for query annotations.

        Returns:
            (Dict): query annotations dictionary

        """
        units_fallback = self._mapper.report_type_map.get('cost_units_fallback')
        annotations = {
            'date': self.date_trunc('usage_start'),
            'cost_units': Coalesce(self._mapper.cost_units_key, Value(units_fallback))
        }
        if self._mapper.usage_units_key:
            units_fallback = self._mapper.report_type_map.get('usage_units_fallback')
            annotations['usage_units'] = Coalesce(self._mapper.usage_units_key, Value(units_fallback))
        # { query_param: database_field_name }
        fields = self._mapper.provider_map.get('annotations')
        prefix_removed_parameters_list = list(map(lambda x: x if ':' not in x else x.split(':', maxsplit=1)[1],
                                                  self.parameters.get('group_by', {}).keys()))
        for q_param, db_field in fields.items():
            if q_param in prefix_removed_parameters_list:
                annotations[q_param] = Concat(db_field, Value(''))
        return annotations

    @property
    def query_table(self):
        """Return the database table to query against."""
        query_table = self._mapper.query_table
        report_type = self.parameters.report_type
        report_group = 'default'

        excluded_filters = set(
            ['time_scope_value', 'time_scope_units', 'resolution', 'limit', 'offset']
        )
        filter_keys = set(self.parameters.get('filter', {}).keys())
        filter_keys = filter_keys.difference(excluded_filters)
        group_by_keys = list(self.parameters.get('group_by', {}).keys())

        # If grouping by more than 1 field, we default to the daily summary table
        if len(group_by_keys) > 1:
            return query_table
        if len(filter_keys) > 1:
            return query_table
        # If filtering on a different field than grouping by, we default to the daily summary table
        if group_by_keys and len(filter_keys.difference(group_by_keys)) != 0:
            return query_table

        # Special Casess for Network and Database Cards in the UI
        service_filter = set(self.parameters.get('filter', {}).get('service', []))
        network_services = [
            'AmazonVPC', 'AmazonCloudFront', 'AmazonRoute53', 'AmazonAPIGateway'
        ]
        database_services = [
            'AmazonRDS', 'AmazonDynamoDB', 'AmazonElastiCache', 'AmazonNeptune',
            'AmazonRedshift', 'AmazonDocumentDB'
        ]
        if report_type == 'costs' and service_filter and not service_filter.difference(network_services):
            report_type = 'network'
        elif report_type == 'costs' and service_filter and not service_filter.difference(database_services):
            report_type = 'database'

        if group_by_keys:
            report_group = group_by_keys[0]
        elif filter_keys and not group_by_keys:
            report_group = list(filter_keys)[0]
        try:
            query_table = self._mapper.views[report_type][report_group]
        except KeyError:
            msg = f'{report_group} for {report_type} has no entry in views. Using the default.'
            LOG.warning(msg)
        return query_table

    def _format_query_response(self):
        """Format the query response with data.

        Returns:
            (Dict): Dictionary response of query params, data, and total

        """
        output = copy.deepcopy(self.parameters.parameters)
        output['data'] = self.query_data
        output['total'] = self.query_sum

        if self._delta:
            output['delta'] = self.query_delta

        return output

    def _build_sum(self, query):
        """Build the sum results for the query."""
        sum_units = {}
        query_sum = self.initialize_totals()
        cost_units_fallback = self._mapper.report_type_map.get('cost_units_fallback')
        usage_units_fallback = self._mapper.report_type_map.get('usage_units_fallback')
        count_units_fallback = self._mapper.report_type_map.get('count_units_fallback')
        if query.exists():
            sum_annotations = {
                'cost_units': Coalesce(self._mapper.cost_units_key, Value(cost_units_fallback))
            }
            if self._mapper.usage_units_key:
                units_fallback = self._mapper.report_type_map.get('usage_units_fallback')
                sum_annotations['usage_units'] = Coalesce(self._mapper.usage_units_key, Value(units_fallback))
            sum_query = query.annotate(**sum_annotations)
            units_value = sum_query.values('cost_units').first().get('cost_units', cost_units_fallback)
            sum_units = {'cost_units': units_value}
            if self._mapper.usage_units_key:
                units_value = sum_query.values('usage_units').first().get('usage_units', usage_units_fallback)
                sum_units['usage_units'] = units_value
            if self._mapper.report_type_map.get('annotations', {}).get('count_units'):
                sum_units['count_units'] = count_units_fallback
            query_sum = self.calculate_total(**sum_units)
        else:
            sum_units['cost_units'] = cost_units_fallback
            if self._mapper.report_type_map.get('annotations', {}).get('count_units'):
                sum_units['count_units'] = count_units_fallback
            if self._mapper.report_type_map.get('annotations', {}).get('usage_units'):
                sum_units['usage_units'] = usage_units_fallback
            query_sum.update(sum_units)
            self._pack_data_object(query_sum, **self._mapper.PACK_DEFINITIONS)
        return query_sum

    def execute_query(self):
        """Execute query and return provided data.

        Returns:
            (Dict): Dictionary response of query params, data, and total

        """
        data = []

        with tenant_context(self.tenant):
            query = self.query_table.objects.filter(self.query_filter)
            query_data = query.annotate(**self.annotations)
            query_group_by = ['date'] + self._get_group_by()
            query_order_by = ['-date', ]
            query_order_by.extend([self.order])

            annotations = self._mapper.report_type_map.get('annotations')
            query_data = query_data.values(*query_group_by).annotate(**annotations)

            if 'account' in query_group_by:
                query_data = query_data.annotate(account_alias=Coalesce(
                    F(self._mapper.provider_map.get('alias')), 'usage_account_id'))

            query_sum = self._build_sum(query)

            if self._limit:
                rank_order = getattr(F(self.order_field), self.order_direction)()
                rank_by_total = Window(
                    expression=RowNumber(),
                    partition_by=F('date'),
                    order_by=rank_order
                )
                query_data = query_data.annotate(rank=rank_by_total)
                query_order_by.insert(1, 'rank')
                query_data = self._ranked_list(query_data)

            if self._delta:
                query_data = self.add_deltas(query_data, query_sum)

            is_csv_output = self.parameters.accept_type and 'text/csv' in self.parameters.accept_type

            query_data, query_group_by = self.strip_label_column_name(
                query_data,
                query_group_by
            )
            query_data = self.order_by(query_data, query_order_by)

            if is_csv_output:
                if self._limit:
                    data = self._ranked_list(list(query_data))
                else:
                    data = list(query_data)
            else:
                groups = copy.deepcopy(query_group_by)
                groups.remove('date')
                data = self._apply_group_by(list(query_data), groups)
                data = self._transform_data(query_group_by, 0, data)

        key_order = list(['units'] + list(annotations.keys()))
        ordered_total = {total_key: query_sum[total_key]
                         for total_key in key_order if total_key in query_sum}
        ordered_total.update(query_sum)

        self.query_sum = ordered_total
        self.query_data = data
        return self._format_query_response()

    def calculate_total(self, **units):
        """Calculate aggregated totals for the query.

        Args:
            units (dict): The units dictionary

        Returns:
            (dict) The aggregated totals for the query

        """
        query_group_by = ['date'] + self._get_group_by()
        query = self.query_table.objects.filter(self.query_filter)
        query_data = query.annotate(**self.annotations)
        query_data = query_data.values(*query_group_by)
        aggregates = self._mapper.report_type_map.get('aggregates')
        counts = None

        if 'count' in aggregates:
            resource_ids = query_data.annotate(
                resource_id=Func(F('resource_ids'), function='unnest')
            ).values_list('resource_id', flat=True).distinct()
            counts = len(resource_ids)

        total_query = query.aggregate(**aggregates)
        for unit_key, unit_value in units.items():
            total_query[unit_key] = unit_value

        if counts:
            total_query['count'] = counts
        self._pack_data_object(total_query, **self._mapper.PACK_DEFINITIONS)

        return total_query
