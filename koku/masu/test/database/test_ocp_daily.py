#
# Copyright 2018 Red Hat, Inc.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

import datetime
from datetime import timedelta
from calendar import monthrange
from masu.database import OCP_REPORT_TABLE_MAP
from masu.database.report_db_accessor_base import ReportDBAccessorBase
from masu.database.reporting_common_db_accessor import ReportingCommonDBAccessor
from tests import MasuTestCase


class OCPDailyTest(MasuTestCase):
    """Test Cases for the OCP Daily and Daily_Summary database tables."""

    # Select schema and open connection with PostgreSQL and SQLAlchemy
    # Establish connection using PostgreSQL server metadata (PostgreSQL, user, password, host, port, database name)
    # Initialize cursor and set search path to schema
    def setUp(self):
        """Establish the database connection."""
        self._datetime_format = '%Y-%m-%d %H:%M:%S'
        self._schema = 'acct10001'
        self.common_accessor = ReportingCommonDBAccessor()
        self.column_map = self.common_accessor.column_map
        self.accessor = ReportDBAccessorBase(
            self._schema, self.column_map
        )
        self.report_schema = self.accessor.report_schema
        print("Connection is successful!")

    # Close connection with PostgreSQL and SQLAlchemy
    def tearDown(self):
        """Close the DB session connection."""
        self.common_accessor.close_session()
        self.accessor.close_connections()
        self.accessor.close_session()
        print("Connection is closed")

    def get_today_date(self):
        return datetime.datetime.now().replace(microsecond=0, second=0, minute=0)

    # Helper raw SQL function to select column data from table with optional query values of row and order by
    def table_select_raw_sql(self, table_name, columns=None, rows=None, order_by=None):
        command = ""
        if columns is not None:
            command = "SELECT {} FROM {};".format(str(columns), str(table_name))
        if rows is not None:
            command = command[:-1] + " WHERE {};".format(str(rows))
        if order_by is not None:
            command = command[:-1] + " ORDER BY {};".format(str(order_by))
        self.accessor._cursor.execute(command)
        data = self.accessor._cursor.fetchall()
        return data

    def get_time_interval(self):
        asc_data = self.table_select_raw_sql(OCP_REPORT_TABLE_MAP['storage_line_item_daily'], "usage_start", None,
                                             "usage_start ASC")
        desc_data = self.table_select_raw_sql(OCP_REPORT_TABLE_MAP['storage_line_item_daily'], "usage_start", None,
                                              "usage_start DESC")
        start_interval = asc_data[0][0].date()
        end_interval = desc_data[0][0].date()
        return start_interval, end_interval

    def date_range(self, start_date, end_date):
        for n in range(int((end_date - start_date).days)):
            yield start_date + timedelta(n)

    # Datetime format util function
    def get_datetime(self, date_val):
        start = "\'" + str(date_val) + " 00:00:00+00\'"
        end = "\'" + str(date_val) + " 23:59:59+00\'"
        return start, end

    def table_select(self, table_name, columns):
        query = self.accessor._get_db_obj_query(
            table_name, columns)
        return query

    # OCP resource daily and daily summary usage/cost data via DB accessor query
    def table_select_by_date(self, table_name, columns, date_val):
        usage_start, usage_end = self.get_datetime(date_val)
        query = self.accessor._get_db_obj_query(
            table_name, columns)
        query_by_date = query.filter_by(usage_start=usage_start)
        return query_by_date

    # Assert raw line item and daily values for OCP storage are correct based on DB accessor queries using SQLAlchemy
    def test_storage_line_item_to_daily(self):
        # database test between STORAGE raw and daily reporting tables
        count = self.table_select_raw_sql(OCP_REPORT_TABLE_MAP['storage_line_item'], "count(*)")[0][0]

        if count == 0:
            self.fail("OCP Storage line item reporting table is empty")

        # ocp storage start datetime field
        report_items = self.table_select(
            OCP_REPORT_TABLE_MAP['report'],
            ["interval_start"])

        # time interval used to check cluster id
        report_period_items = self.table_select(
            OCP_REPORT_TABLE_MAP['report_period'],
            ["cluster_id", "report_period_start", "report_period_end"])

        # get ocp storage line item fields
        storage_line_items = self.table_select(
            OCP_REPORT_TABLE_MAP['storage_line_item'],
            ["namespace", "pod", "persistentvolumeclaim", "persistentvolume",
             "storageclass", "persistentvolumeclaim_capacity_bytes", "persistentvolumeclaim_capacity_byte_seconds",
             "volume_request_storage_byte_seconds", "persistentvolumeclaim_usage_byte_seconds",
             "persistentvolume_labels", "persistentvolumeclaim_labels"])

        if storage_line_items.count() == 0:
            self.fail("OCP Storage line item reporting table is empty")

        # initialize list of dictionaries to store each unique line item
        storage_list_dict = [{"namespace": storage_line_items[0][0], "pod": storage_line_items[0][1],
                              "persistentvolumeclaim": storage_line_items[0][2],
                              "persistentvolume": storage_line_items[0][3],
                              "storageclass": storage_line_items[0][4],
                              "persistentvolumeclaim_capacity_bytes": storage_line_items[0][5],
                              "persistentvolumeclaim_capacity_byte_seconds": storage_line_items[0][6],
                              "volume_request_storage_byte_seconds": storage_line_items[0][7],
                              "persistentvolumeclaim_usage_byte_seconds": storage_line_items[0][8],
                              "persistentvolume_labels": storage_line_items[0][9],
                              "persistentvolumeclaim_labels": storage_line_items[0][10],
                              "interval_start": report_items[0][0], "cluster_id": report_period_items[0][0]}]

        # counter to keep iterate through length of storage_list_dict
        daily_counter = 0
        # counter for index within report_period_items table
        report_counter = 0
        # get current date of first line item
        curr_date = report_items[0][0].date()
        # index of ocp storage line items
        items_counter = 1

        # iterate through all line items based on count value of reporting table
        while items_counter < count:
            # if current date needs to be iterated forward, then assert field comparison between raw and daily first
            if curr_date != report_items[items_counter][0].date():
                # get ocp storage daily fields
                daily_storage = self.table_select_by_date(
                    OCP_REPORT_TABLE_MAP['storage_line_item_daily'],
                    ["cluster_id", "namespace", "pod", "persistentvolumeclaim", "persistentvolume",
                     "storageclass", "persistentvolumeclaim_capacity_bytes",
                     "persistentvolumeclaim_capacity_byte_seconds",
                     "volume_request_storage_byte_seconds", "persistentvolumeclaim_usage_byte_seconds",
                     "persistentvolume_labels", "persistentvolumeclaim_labels"], curr_date)

                if daily_storage.count() == 0:
                    self.fail("OCP Storage daily reporting table is empty")

                # print current date of line item
                print(curr_date)

                # assertion between the total summation of line item values and daily values for the current date
                while daily_counter < len(storage_list_dict):
                    try:
                        self.assertEqual(storage_list_dict[daily_counter]["persistentvolumeclaim_capacity_bytes"],
                                         daily_storage[daily_counter][6])
                        self.assertEqual(storage_list_dict[daily_counter]["persistentvolumeclaim_capacity_byte_seconds"],
                                         daily_storage[daily_counter][7])
                        self.assertEqual(storage_list_dict[daily_counter]["volume_request_storage_byte_seconds"],
                                         daily_storage[daily_counter][8])
                        self.assertEqual(storage_list_dict[daily_counter]["persistentvolumeclaim_usage_byte_seconds"],
                                         daily_storage[daily_counter][9])
                        daily_counter += 1
                        print("OCP Storage Raw vs Daily tests have passed!")
                    except AssertionError as error:
                        print(error)
                        self.fail("Test assertion for " + str(curr_date) + " has failed")

                # get current date of line item
                curr_date = report_items[items_counter][0].date()

                # increment to correct report time interval
                while curr_date < report_period_items[report_counter][1].date():
                    report_counter += 1

                # re-initialize list of dictionaries with new line item and repeat while loop
                storage_list_dict = [
                    {"namespace": storage_line_items[items_counter][0], "pod": storage_line_items[items_counter][1],
                     "persistentvolumeclaim": storage_line_items[items_counter][2],
                     "persistentvolume": storage_line_items[items_counter][3],
                     "storageclass": storage_line_items[items_counter][4],
                     "persistentvolumeclaim_capacity_bytes": storage_line_items[items_counter][5],
                     "persistentvolumeclaim_capacity_byte_seconds": storage_line_items[items_counter][6],
                     "volume_request_storage_byte_seconds": storage_line_items[items_counter][7],
                     "persistentvolumeclaim_usage_byte_seconds": storage_line_items[items_counter][8],
                     "persistentvolume_labels": storage_line_items[items_counter][9],
                     "persistentvolumeclaim_labels": storage_line_items[items_counter][10],
                     "interval_start": report_items[items_counter][0],
                     "cluster_id": report_period_items[report_counter][0]}]
                daily_counter = 0
                items_counter += 1

            # else, continue to sum and max fields for next hour of current day
            else:
                # counter for iterating through storage_list_dict (if it is length > 1)
                dict_counter = 0
                # flag to indicate that fields of next line item match an entry in our storage_list_dict and values
                # are summed or maxed appropriately
                flag = 0

                # iterate through storage_list_dict entries (usually only one line item bc database is sorted by date)
                while dict_counter < len(storage_list_dict):
                    # check if group by fields match
                    if (storage_list_dict[dict_counter]["namespace"] == storage_line_items[items_counter][0] and
                            storage_list_dict[dict_counter]["pod"] == storage_line_items[items_counter][1] and
                            storage_list_dict[dict_counter]["persistentvolumeclaim"] == storage_line_items[items_counter][2] and
                            storage_list_dict[dict_counter]["persistentvolume"] == storage_line_items[items_counter][3] and
                            storage_list_dict[dict_counter]["storageclass"] == storage_line_items[items_counter][4] and
                            storage_list_dict[dict_counter]["persistentvolume_labels"] == storage_line_items[items_counter][9] and
                            storage_list_dict[dict_counter]["persistentvolumeclaim_labels"] == storage_line_items[items_counter][10] and
                            storage_list_dict[dict_counter]["cluster_id"] == report_period_items[report_counter][0] and
                            storage_list_dict[dict_counter]["interval_start"].date() == report_items[items_counter][0].date()):

                        # sum or max values based on database line item to daily report processing
                        cap_bytes = max(
                            storage_list_dict[dict_counter]["persistentvolumeclaim_capacity_bytes"],
                            storage_line_items[items_counter][5])
                        cap_bytes_sec = storage_list_dict[dict_counter]["persistentvolumeclaim_capacity_byte_seconds"] + \
                                        storage_line_items[items_counter][6]
                        storage_bytes_sec = storage_list_dict[dict_counter]["volume_request_storage_byte_seconds"] + \
                                            storage_line_items[items_counter][7]
                        usage_bytes_sec = storage_list_dict[dict_counter]["persistentvolumeclaim_usage_byte_seconds"] + \
                                          storage_line_items[items_counter][8]

                        # update the storage_list_dict entry
                        dic_entry_temp = {"persistentvolumeclaim_capacity_bytes": cap_bytes,
                                          "persistentvolumeclaim_capacity_byte_seconds": cap_bytes_sec,
                                          "volume_request_storage_byte_seconds": storage_bytes_sec,
                                          "persistentvolumeclaim_usage_byte_seconds": usage_bytes_sec}
                        storage_list_dict[dict_counter].update(dic_entry_temp)

                        # set flag
                        flag = 1
                        break
                    dict_counter += 1

                # unusual case: if set of fields did not match any existing entries in dictionaries, then create new
                # entry within usage_list_dict
                if flag == 0:
                    storage_list_dict.append({"namespace": storage_line_items[items_counter][0],
                                              "pod": storage_line_items[items_counter][1],
                                              "persistentvolumeclaim": storage_line_items[items_counter][2],
                                              "persistentvolume": storage_line_items[items_counter][3],
                                              "storageclass": storage_line_items[items_counter][4],
                                              "persistentvolumeclaim_capacity_bytes": storage_line_items[items_counter][5],
                                              "persistentvolumeclaim_capacity_byte_seconds":
                                                  storage_line_items[items_counter][6],
                                              "volume_request_storage_byte_seconds": storage_line_items[items_counter][7],
                                              "persistentvolumeclaim_usage_byte_seconds":
                                                  storage_line_items[items_counter][8],
                                              "persistentvolume_labels": storage_line_items[items_counter][9],
                                              "persistentvolumeclaim_labels": storage_line_items[items_counter][10],
                                              "interval_start": report_items[items_counter][0],
                                              "cluster_id": report_period_items[report_counter][0]})
                items_counter += 1

    # Assert raw line item and daily values for OCP usage are correct based on DB accessor queries using SQLAlchemy
    def test_usage_line_item_to_daily(self):
        # database test between USAGE raw and daily reporting tables
        count = self.table_select_raw_sql(OCP_REPORT_TABLE_MAP['line_item'], "count(*)")[0][0]

        if count == 0:
            self.fail("OCP Usage line item reporting table is empty")

        # ocp usage start datetime field
        report_items = self.table_select(
            OCP_REPORT_TABLE_MAP['report'],
            ["interval_start"])

        # time interval used to check cluster id
        report_period_items = self.table_select(
            OCP_REPORT_TABLE_MAP['report_period'],
            ["cluster_id", "report_period_start", "report_period_end"])

        # get ocp usage line item fields
        usage_line_items = self.table_select(
            OCP_REPORT_TABLE_MAP['line_item'],
            ["namespace", "pod", "node", "pod_usage_cpu_core_seconds", "pod_request_cpu_core_seconds",
             "pod_limit_cpu_core_seconds", "pod_usage_memory_byte_seconds",
             "pod_request_memory_byte_seconds", "pod_limit_memory_byte_seconds",
             "node_capacity_cpu_core_seconds", "node_capacity_memory_bytes", "node_capacity_cpu_cores",
             "node_capacity_memory_byte_seconds", "pod_labels", "resource_id"])

        if usage_line_items.count() == 0:
            self.fail("OCP Usage line item reporting table is empty")

        # initialize list of dictionaries to store each unique line item
        usage_list_dict = [{"namespace": usage_line_items[0][0], "pod": usage_line_items[0][1],
                            "node": usage_line_items[0][2], "pod_usage_cpu_core_seconds": usage_line_items[0][3],
                            "pod_request_cpu_core_seconds": usage_line_items[0][4],
                            "pod_limit_cpu_core_seconds": usage_line_items[0][5],
                            "pod_usage_memory_byte_seconds": usage_line_items[0][6],
                            "pod_request_memory_byte_seconds": usage_line_items[0][7],
                            "pod_limit_memory_byte_seconds": usage_line_items[0][8],
                            "node_capacity_cpu_core_seconds": usage_line_items[0][9],
                            "node_capacity_memory_bytes": usage_line_items[0][10],
                            "node_capacity_cpu_cores": usage_line_items[0][11],
                            "node_capacity_memory_byte_seconds": usage_line_items[0][12],
                            "pod_labels": usage_line_items[0][13], "resource_id": usage_line_items[0][14],
                            "interval_start": report_items[0][0], "cluster_id": report_period_items[0][0]}]

        # counter to keep iterate through length of usage_list_dict
        daily_counter = 0
        # counter for index within report_period_items table
        report_counter = 0
        # get current date of first line item
        curr_date = report_items[0][0].date()
        # index of ocp usage line items
        items_counter = 1

        # iterate through all line items based on count value of reporting table
        while items_counter < count:
            # if current date needs to be iterated forward, then assert field comparison between raw and daily first
            if curr_date != report_items[items_counter][0].date():
                # get ocp usage daily fields
                daily_usage = self.table_select_by_date(
                    OCP_REPORT_TABLE_MAP['line_item_daily'],
                    ["cluster_id", "namespace", "pod", "node", "pod_usage_cpu_core_seconds",
                     "pod_request_cpu_core_seconds",
                     "pod_limit_cpu_core_seconds", "pod_usage_memory_byte_seconds",
                     "pod_request_memory_byte_seconds", "pod_limit_memory_byte_seconds",
                     "node_capacity_cpu_cores",
                     "node_capacity_cpu_core_seconds", "node_capacity_memory_bytes",
                     "node_capacity_memory_byte_seconds", "pod_labels", "resource_id"], curr_date)

                # print current date of line item
                print(curr_date)

                # assertion between the total summation of line item values and daily values for the current date
                while daily_counter < len(usage_list_dict):
                    try:
                        self.assertEqual(usage_list_dict[daily_counter]["cluster_id"],
                                         daily_usage[daily_counter][0])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_usage_cpu_core_seconds"],
                                         daily_usage[daily_counter][4])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_request_cpu_core_seconds"],
                                         daily_usage[daily_counter][5])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_limit_cpu_core_seconds"],
                                         daily_usage[daily_counter][6])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_usage_memory_byte_seconds"],
                                         daily_usage[daily_counter][7])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_request_memory_byte_seconds"],
                                         daily_usage[daily_counter][8])
                        self.assertEqual(usage_list_dict[daily_counter]["pod_limit_memory_byte_seconds"],
                                         daily_usage[daily_counter][9])
                        self.assertEqual(usage_list_dict[daily_counter]["node_capacity_cpu_core_seconds"],
                                         daily_usage[daily_counter][11])
                        self.assertEqual(usage_list_dict[daily_counter]["node_capacity_memory_bytes"],
                                         daily_usage[daily_counter][12])
                        self.assertEqual(usage_list_dict[daily_counter]["node_capacity_cpu_cores"],
                                         daily_usage[daily_counter][10])
                        self.assertEqual(usage_list_dict[daily_counter]["node_capacity_memory_byte_seconds"],
                                         daily_usage[daily_counter][13])
                        daily_counter += 1
                        print("OCP Usage Raw vs Daily tests have passed!")
                    except AssertionError as error:
                        print(error)
                        self.fail("Test assertion for " + str(curr_date) + " has failed")

                # get current date of line item
                curr_date = report_items[items_counter][0].date()

                # increment to correct report time interval
                while curr_date < report_period_items[report_counter][1].date():
                    report_counter += 1

                # re-initialize list of dictionaries with new line item and repeat while loop
                usage_list_dict = [{"namespace": usage_line_items[items_counter][0],
                                    "pod": usage_line_items[items_counter][1],
                                    "node": usage_line_items[items_counter][2],
                                    "pod_usage_cpu_core_seconds": usage_line_items[items_counter][3],
                                    "pod_request_cpu_core_seconds": usage_line_items[items_counter][4],
                                    "pod_limit_cpu_core_seconds": usage_line_items[items_counter][5],
                                    "pod_usage_memory_byte_seconds": usage_line_items[items_counter][6],
                                    "pod_request_memory_byte_seconds": usage_line_items[items_counter][7],
                                    "pod_limit_memory_byte_seconds": usage_line_items[items_counter][8],
                                    "node_capacity_cpu_core_seconds": usage_line_items[items_counter][9],
                                    "node_capacity_memory_bytes": usage_line_items[items_counter][10],
                                    "node_capacity_cpu_cores": usage_line_items[items_counter][11],
                                    "node_capacity_memory_byte_seconds": usage_line_items[items_counter][12],
                                    "pod_labels": usage_line_items[items_counter][13],
                                    "resource_id": usage_line_items[items_counter][14],
                                    "interval_start": report_items[items_counter][0],
                                    "cluster_id": report_period_items[report_counter][0]}]
                daily_counter = 0
                items_counter += 1

            # else, continue to sum and max fields for next hour of current day
            else:
                # counter for iterating through usage_list_dict (if it is length > 1)
                dict_counter = 0
                # flag to indicate that fields of next line item match an entry in our usage_list_dict and values
                # are summed or maxed appropriately
                flag = 0

                # iterate through usage_list_dict entries (usually only one line item bc database is sorted by date)
                while dict_counter < len(usage_list_dict):
                    # check if group by fields match
                    if (usage_list_dict[dict_counter]["namespace"] == usage_line_items[items_counter][0] and
                            usage_list_dict[dict_counter]["pod"] == usage_line_items[items_counter][1] and
                            usage_list_dict[dict_counter]["node"] == usage_line_items[items_counter][2] and
                            usage_list_dict[dict_counter]["pod_labels"] == usage_line_items[items_counter][13] and
                            usage_list_dict[dict_counter]["resource_id"] == usage_line_items[items_counter][14] and
                            usage_list_dict[dict_counter]["cluster_id"] == report_period_items[report_counter][0] and
                            usage_list_dict[dict_counter]["interval_start"].date() == report_items[items_counter][0].date()):

                        # sum or max values based on database line item to daily report processing
                        cpu_usage = usage_list_dict[dict_counter]["pod_usage_cpu_core_seconds"] + \
                                        usage_line_items[items_counter][3]
                        cup_request = usage_list_dict[dict_counter]["pod_request_cpu_core_seconds"] + \
                                        usage_line_items[items_counter][4]
                        cpu_limit = usage_list_dict[dict_counter]["pod_limit_cpu_core_seconds"] + \
                                        usage_line_items[items_counter][5]
                        mem_usage = usage_list_dict[dict_counter]["pod_usage_memory_byte_seconds"] + \
                                        usage_line_items[items_counter][6]
                        mem_request = usage_list_dict[dict_counter]["pod_request_memory_byte_seconds"] + \
                                        usage_line_items[items_counter][7]
                        mem_limit = usage_list_dict[dict_counter]["pod_limit_memory_byte_seconds"] + \
                                        usage_line_items[items_counter][8]
                        cpu_core_sec = usage_list_dict[dict_counter]["node_capacity_cpu_core_seconds"] + \
                                        usage_line_items[items_counter][9]
                        mem_bytes = max(usage_list_dict[dict_counter]["node_capacity_memory_bytes"],
                                        usage_line_items[items_counter][10])
                        cpu_cores = max(usage_list_dict[dict_counter]["node_capacity_cpu_cores"],
                                        usage_line_items[items_counter][11])
                        mem_byte_sec = usage_list_dict[dict_counter]["node_capacity_memory_byte_seconds"] + \
                                        usage_line_items[items_counter][12]

                        # update the usage_list_dict entry
                        dic_entry_temp = {"pod_usage_cpu_core_seconds": cpu_usage,
                                          "pod_request_cpu_core_seconds": cup_request,
                                          "pod_limit_cpu_core_seconds": cpu_limit,
                                          "pod_usage_memory_byte_seconds": mem_usage,
                                          "pod_request_memory_byte_seconds": mem_request,
                                          "pod_limit_memory_byte_seconds": mem_limit,
                                          "node_capacity_cpu_core_seconds": cpu_core_sec,
                                          "node_capacity_memory_bytes": mem_bytes,
                                          "node_capacity_cpu_cores": cpu_cores,
                                          "node_capacity_memory_byte_seconds": mem_byte_sec}
                        usage_list_dict[dict_counter].update(dic_entry_temp)

                        # set flag
                        flag = 1
                        break
                    dict_counter += 1

                # unusual case: if set of fields did not match any existing entries in dictionaries, then create new
                # entry within usage_list_dict
                if flag == 0:
                    usage_list_dict.append({"namespace": usage_line_items[items_counter][0],
                                            "pod": usage_line_items[items_counter][1],
                                            "node": usage_line_items[items_counter][2],
                                            "pod_usage_cpu_core_seconds": usage_line_items[items_counter][3],
                                            "pod_request_cpu_core_seconds": usage_line_items[items_counter][4],
                                            "pod_limit_cpu_core_seconds": usage_line_items[items_counter][5],
                                            "pod_usage_memory_byte_seconds": usage_line_items[items_counter][6],
                                            "pod_request_memory_byte_seconds": usage_line_items[items_counter][7],
                                            "pod_limit_memory_byte_seconds": usage_line_items[items_counter][8],
                                            "node_capacity_cpu_core_seconds": usage_line_items[items_counter][9],
                                            "node_capacity_memory_bytes": usage_line_items[items_counter][10],
                                            "node_capacity_cpu_cores": usage_line_items[items_counter][11],
                                            "node_capacity_memory_byte_seconds": usage_line_items[items_counter][12],
                                            "pod_labels": usage_line_items[items_counter][13],
                                            "resource_id": usage_line_items[items_counter][14],
                                            "interval_start": report_items[items_counter][0],
                                            "cluster_id": report_period_items[report_counter][0]})
                items_counter += 1

        print("All Raw vs Daily tests have passed!")

    # Assert daily and daily summary values are correct based on DB accessor queries using SQLAlchemy
    def test_daily_to_summary(self):
        # database test between daily and daily_summary reporting tables for usage and storage
        start_interval, end_interval = (self.get_time_interval())
        today = self.get_today_date().date()
        if end_interval == today:
            end_interval = today
        for date_val in self.date_range(start_interval, end_interval):
            print("Date: " + str(date_val))
            parse_date = datetime.datetime.strptime(str(date_val), "%Y-%m-%d")
            daily_storage = self.table_select_by_date(
                OCP_REPORT_TABLE_MAP['storage_line_item_daily'],
                ["persistentvolume_labels", "persistentvolumeclaim_labels", "persistentvolumeclaim_capacity_bytes",
                 "persistentvolumeclaim_capacity_byte_seconds", "volume_request_storage_byte_seconds",
                 "persistentvolumeclaim_usage_byte_seconds"], date_val)
            daily_summary_storage = self.table_select_by_date(
                OCP_REPORT_TABLE_MAP['storage_line_item_daily_summary'],
                ["volume_labels", "persistentvolumeclaim_capacity_gigabyte",
                 "persistentvolumeclaim_capacity_gigabyte_months", "volume_request_storage_gigabyte_months",
                 "persistentvolumeclaim_usage_gigabyte_months"], date_val)

            if daily_storage.count() == 0:
                self.fail("OCP Storage daily reporting table is empty")
            if daily_summary_storage.count() == 0:
                self.fail("OCP Storage daily summary reporting table is empty")

            cap_giga = float(daily_storage[0][2]) * (2 ** (-30))
            cap_giga_months = float(daily_storage[0][3]) / 86400 * \
                              monthrange(parse_date.year, parse_date.month)[1] * (
                                      2 ** (-30))
            storage_giga_months = float(daily_storage[0][4]) / 86400 * \
                                  monthrange(parse_date.year, parse_date.month)[1] * (2 ** (-30))
            usage_giga_months = float(daily_storage[0][5]) / 86400 * \
                                monthrange(parse_date.year, parse_date.month)[1] * (
                                        2 ** (-30))

            labels = dict(daily_storage[0][0])
            labels.update(daily_storage[0][1])

            try:
                self.assertEqual(labels, daily_summary_storage[0][0])
                self.assertEqual(cap_giga, daily_summary_storage[0][1])
                self.assertEqual(cap_giga_months, daily_summary_storage[0][2])
                self.assertEqual(storage_giga_months, daily_summary_storage[0][3])
                self.assertEqual(usage_giga_months, daily_summary_storage[0][4])
                print("OCP Storage Daily vs Daily Summary tests have passed!")
            except AssertionError as error:
                print(error)
                self.fail("Test assertion for " + str(date_val) + " has failed")

            daily_usage = self.table_select_by_date(
                OCP_REPORT_TABLE_MAP['line_item_daily'],
                ["pod_usage_cpu_core_seconds", "pod_request_cpu_core_seconds",
                 "pod_limit_cpu_core_seconds", "pod_usage_memory_byte_seconds",
                 "pod_request_memory_byte_seconds", "pod_limit_memory_byte_seconds",
                 "node_capacity_cpu_core_seconds", "node_capacity_memory_bytes",
                 "node_capacity_memory_byte_seconds", "cluster_capacity_cpu_core_seconds",
                 "cluster_capacity_memory_byte_seconds", "total_capacity_cpu_core_seconds",
                 "total_capacity_memory_byte_seconds"], date_val)
            daily_summary_usage = self.table_select_by_date(
                OCP_REPORT_TABLE_MAP['line_item_daily_summary'],
                ["pod_usage_cpu_core_hours", "pod_request_cpu_core_hours",
                 "pod_limit_cpu_core_hours", "pod_usage_memory_gigabyte_hours",
                 "pod_request_memory_gigabyte_hours", "pod_limit_memory_gigabyte_hours",
                 "node_capacity_cpu_core_hours", "node_capacity_memory_gigabytes",
                 "node_capacity_memory_gigabyte_hours", "cluster_capacity_cpu_core_hours",
                 "cluster_capacity_memory_gigabyte_hours", "total_capacity_cpu_core_hours",
                 "total_capacity_memory_gigabyte_hours"], date_val)

            if daily_usage.count() == 0:
                self.fail("OCP Usage daily reporting table is empty")
            if daily_summary_usage.count() == 0:
                self.fail("OCP Usage daily summary reporting table is empty")

            try:
                self.assertEqual(float(daily_usage[0][0]) / 3600, daily_summary_usage[0][0])
                self.assertEqual(float(daily_usage[0][1]) / 3600, daily_summary_usage[0][1])
                self.assertEqual(float(daily_usage[0][2]) / 3600, daily_summary_usage[0][2])
                self.assertEqual(float(daily_usage[0][3]) / 3600 * (2 ** (-30)), daily_summary_usage[0][3])
                self.assertEqual(float(daily_usage[0][4]) / 3600 * (2 ** (-30)), daily_summary_usage[0][4])
                self.assertEqual(float(daily_usage[0][5]) / 3600 * (2 ** (-30)), daily_summary_usage[0][5])
                self.assertEqual(float(daily_usage[0][6]) / 3600, daily_summary_usage[0][6])
                self.assertEqual(float(daily_usage[0][7]) * (2 ** (-30)), daily_summary_usage[0][7])
                self.assertEqual(float(daily_usage[0][8]) / 3600 * (2 ** (-30)), daily_summary_usage[0][8])
                self.assertEqual(float(daily_usage[0][9]) / 3600, daily_summary_usage[0][9])
                self.assertEqual(float(daily_usage[0][10]) / 3600 * (2 ** (-30)), daily_summary_usage[0][10])
                self.assertEqual(float(daily_usage[0][11]) / 3600, daily_summary_usage[0][11])
                self.assertEqual(float(daily_usage[0][12]) / 3600 * (2 ** (-30)), daily_summary_usage[0][12])
                print("OCP Usage Daily vs Daily Summary tests have passed!")
            except AssertionError as error:
                print(error)
                self.fail("Test assertion for " + str(date_val) + " has failed")

        print("All OCP Daily vs Daily Summary tests have passed!")
        print("All OCP reporting database tests have passed!")


# test script
psql = OCPDailyTest()
psql.setUp()
psql.test_usage_line_item_to_daily()
psql.test_storage_line_item_to_daily()
psql.test_daily_to_summary()
psql.tearDown()
