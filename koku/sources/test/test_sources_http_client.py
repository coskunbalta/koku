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
"""Test the Sources HTTP Client."""
from unittest.mock import patch

import requests
import requests_mock
from django.test import TestCase
from faker import Faker
from sources.config import Config
from sources.sources_http_client import SourcesHTTPClient, SourcesHTTPClientError

faker = Faker()


class SourcesHTTPClientTest(TestCase):
    """Test cases for SourcesHTTPClient."""

    def setUp(self):
        """Test case setup."""
        super().setUp()
        self.name = 'Test Source'
        self.application_type = 2
        self.source_id = 1
        self.authentication = 'testauth'

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_details(self):
        """Test to get source details."""
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/sources/{self.source_id}',
                  status_code=200, json={'name': self.name})
            response = client.get_source_details()
            self.assertEqual(response.get('name'), self.name)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_details_unsuccessful(self):
        """Test to get source details unsuccessfully."""
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/sources/{self.source_id}',
                  status_code=404)
            with self.assertRaises(SourcesHTTPClientError):
                client.get_source_details()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_cost_management_application_type_id(self):
        """Test to get application type id."""
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/application_types?filter[name]=/insights/platform/cost-management',
                  status_code=200, json={'data': [{'id': self.application_type}]})
            response = client.get_cost_management_application_type_id()
            self.assertEqual(response, self.application_type)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_cost_management_application_type_id_error(self):
        """Test to get application type id with error."""
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/application_types?filter[name]=/insights/platform/cost-management',
                  exc=requests.exceptions.RequestException)
            with self.assertRaises(SourcesHTTPClientError):
                client.get_cost_management_application_type_id()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_cost_management_application_type_id_not_found(self):
        """Test to get application type id with invalid prefix."""
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/application_types?filter[name]=/insights/platform/cost-management',
                  status_code=404, json={'data': [{'id': self.application_type}]})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_cost_management_application_type_id()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_type_name(self):
        """Test to get source type name from type id."""
        source_type_id = 3
        mock_source_name = 'fakesource'
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/source_types?filter[id]={source_type_id}',
                  status_code=200, json={'data': [{'name': mock_source_name}]})
            response = client.get_source_type_name(source_type_id)
            self.assertEqual(response, mock_source_name)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_type_name_error(self):
        """Test to get source type name from type id with error."""
        source_type_id = 3
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/source_types?filter[id]={source_type_id}',
                  exc=requests.exceptions.RequestException)
            with self.assertRaises(SourcesHTTPClientError):
                client.get_source_type_name(source_type_id)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_type_name_non_200(self):
        """Test to get source type name from type id with bad response."""
        source_type_id = 3
        mock_source_name = 'fakesource'
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/source_types?filter[id]={source_type_id}',
                  status_code=404, json={'data': [{'name': mock_source_name}]})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_source_type_name(source_type_id)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_aws_role_arn(self):
        """Test to get AWS Role ARN from authentication service."""
        resource_id = 2
        authentication_id = 3
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={self.source_id}',
                  status_code=200, json={'data': [{'id': resource_id}]})
            m.get((f'http://www.sources.com/api/v1.0/authentications?filter[resource_type]=Endpoint'
                  f'&[authtype]=arn&[resource_id]={resource_id}'),
                  status_code=200, json={'data': [{'id': authentication_id}]})
            m.get((f'http://www.sources.com/internal/v1.0/authentications/{authentication_id}'
                  f'?expose_encrypted_attribute[]=password'),
                  status_code=200, json={'password': self.authentication})
            response = client.get_aws_role_arn()
            self.assertEqual(response, self.authentication)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_aws_role_arn_no_auth(self):
        """Test to get AWS Role ARN from authentication service with auth not ready."""
        resource_id = 2
        authentication_id = 3
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={self.source_id}',
                  status_code=200, json={'data': [{'id': resource_id}]})
            m.get((f'http://www.sources.com/api/v1.0/authentications?filter[resource_type]=Endpoint'
                  f'&[authtype]=arn&[resource_id]={resource_id}'),
                  status_code=200, json={'data': []})
            m.get((f'http://www.sources.com/internal/v1.0/authentications/{authentication_id}'
                  f'?expose_encrypted_attribute[]=password'),
                  status_code=200, json={'password': self.authentication})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_aws_role_arn()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_azure_credentials(self):
        """Test to get Azure credentials from authentication service."""
        resource_id = 2
        authentication_id = 3

        authentication = 'testclientcreds'
        username = 'test_user'
        tenent_id = 'test_tenent_id'
        authentications_response = {'id': authentication_id, 'username': username,
                                    'extra': {'azure': {'tenant_id': tenent_id}}}

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={self.source_id}',
                  status_code=200, json={'data': [{'id': resource_id}]})
            m.get((f'http://www.sources.com/api/v1.0/authentications?filter[resource_type]=Endpoint'
                  f'&[authtype]=tenant_id_client_id_client_secret&[resource_id]={resource_id}'),
                  status_code=200, json={'data': [authentications_response]})
            m.get((f'http://www.sources.com/internal/v1.0/authentications/{authentication_id}'
                  f'?expose_encrypted_attribute[]=password'),
                  status_code=200, json={'password': authentication})
            response = client.get_azure_credentials()

            self.assertEqual(response, {'client_id': username,
                                        'client_secret': authentication,
                                        'tenant_id': tenent_id})

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_azure_credentials_no_auth(self):
        """Test to get Azure credentials from authentication service with auth not ready."""
        resource_id = 2
        authentication_id = 3

        authentication = 'testclientcreds'

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=self.source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={self.source_id}',
                  status_code=200, json={'data': [{'id': resource_id}]})
            m.get((f'http://www.sources.com/api/v1.0/authentications?filter[resource_type]=Endpoint'
                  f'&[authtype]=tenant_id_client_id_client_secret&[resource_id]={resource_id}'),
                  status_code=200, json={'data': []})
            m.get((f'http://www.sources.com/internal/v1.0/authentications/{authentication_id}'
                  f'?expose_encrypted_attribute[]=password'),
                  status_code=200, json={'password': authentication})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_azure_credentials()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_endpoint_id(self):
        """Test to get endpoint_id from Source_id."""
        resource_id = 2
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={source_id}',
                  status_code=200, json={'data': [{'id': resource_id}]})
            response = client.get_endpoint_id()
            self.assertEqual(response, resource_id)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_endpoint_id_no_data(self):
        """Test to get endpoint_id from Source_id with no data in response."""
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={source_id}',
                  status_code=200, json={'data': []})
            self.assertIsNone(client.get_endpoint_id())

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_endpoint_id_misconfigured(self):
        """Test to get endpoint_id from Source_id with route not found."""
        resource_id = 2
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[source_id]={source_id}',
                  status_code=404, json={'data': [{'id': resource_id}]})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_endpoint_id()

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_id_from_endpoint_id(self):
        """Test to get source_id from resource_id."""
        resource_id = 2
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[id]={resource_id}',
                  status_code=200, json={'data': [{'source_id': source_id}]})
            response = client.get_source_id_from_endpoint_id(resource_id)
            self.assertEqual(response, source_id)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_id_from_endpoint_id_no_data(self):
        """Test to get source_id from resource_id with no data in response."""
        resource_id = 2
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[id]={resource_id}',
                  status_code=200, json={'data': []})
            self.assertIsNone(client.get_source_id_from_endpoint_id(resource_id))

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_get_source_id_from_endpoint_id_misconfigured(self):
        """Test to get source_id from resource_id with route not found."""
        resource_id = 2
        source_id = 3

        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=source_id)
        with requests_mock.mock() as m:
            m.get(f'http://www.sources.com/api/v1.0/endpoints?filter[id]={resource_id}',
                  status_code=404, json={'data': [{'id': resource_id}]})
            with self.assertRaises(SourcesHTTPClientError):
                client.get_source_id_from_endpoint_id(resource_id)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_set_source_status(self):
        """Test to set source status."""
        test_source_id = 1
        application_type_id = 2
        application_id = 3
        status = 'available'
        error_msg = 'my error'
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=test_source_id)
        with requests_mock.mock() as m:
            m.get((f'http://www.sources.com/api/v1.0/applications?'
                   f'filter[application_type_id]={application_type_id}&filter[source_id]={test_source_id}'),
                  status_code=200, json={'data': [{'id': application_id}]})
            m.patch(f'http://www.sources.com/api/v1.0/applications/{application_id}',
                    status_code=204, json={'availability_status': status, 'availability_status_error': str(error_msg)})
            response = client.set_source_status(error_msg, application_type_id)
            self.assertTrue(response)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_set_source_status_source_deleted(self):
        """Test to set source status after source has been deleted."""
        test_source_id = 1
        application_type_id = 2
        error_msg = 'my error'
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=test_source_id)
        with requests_mock.mock() as m:
            m.get((f'http://www.sources.com/api/v1.0/applications?'
                   f'filter[application_type_id]={application_type_id}&filter[source_id]={test_source_id}'),
                  status_code=200, json={'data': []})
            response = client.set_source_status(error_msg, application_type_id)
            self.assertFalse(response)

    @patch.object(Config, 'SOURCES_API_URL', 'http://www.sources.com')
    def test_set_source_status_patch_fail(self):
        """Test to set source status where the patch fails."""
        test_source_id = 1
        application_type_id = 2
        application_id = 3
        status = 'available'
        error_msg = 'my error'
        client = SourcesHTTPClient(auth_header=Config.SOURCES_FAKE_HEADER, source_id=test_source_id)
        with requests_mock.mock() as m:
            m.get((f'http://www.sources.com/api/v1.0/applications?'
                   f'filter[application_type_id]={application_type_id}&filter[source_id]={test_source_id}'),
                  status_code=200, json={'data': [{'id': application_id}]})
            m.patch(f'http://www.sources.com/api/v1.0/applications/{application_id}',
                    status_code=400, json={'availability_status': status, 'availability_status_error': str(error_msg)})
            with self.assertRaises(SourcesHTTPClientError):
                client.set_source_status(error_msg, application_type_id)
