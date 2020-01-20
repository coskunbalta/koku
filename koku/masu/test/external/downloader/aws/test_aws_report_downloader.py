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

"""Test the AWS S3 utility functions."""

import io
import logging
import os.path
import random
import shutil
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from faker import Faker

from api.models import Provider
from masu.config import Config
from masu.database.report_manifest_db_accessor import ReportManifestDBAccessor
from masu.exceptions import MasuProviderError
from masu.external import AWS_REGIONS
from masu.external.date_accessor import DateAccessor
from masu.external.downloader.aws.aws_report_downloader import (
    AWSReportDownloader,
    AWSReportDownloaderError,
    AWSReportDownloaderNoFileError,
)
from masu.external.report_downloader import ReportDownloader
from masu.test import MasuTestCase
from masu.test.external.downloader.aws import fake_arn

DATA_DIR = Config.TMP_DIR
FAKE = Faker()
CUSTOMER_NAME = FAKE.word()
REPORT = FAKE.word()
BUCKET = FAKE.word()
PREFIX = FAKE.word()

# the cn endpoints aren't supported by moto, so filter them out
AWS_REGIONS = list(filter(lambda reg: not reg.startswith('cn-'), AWS_REGIONS))
REGION = random.choice(AWS_REGIONS)


def mock_kwargs_error(**kwargs):
    """Mock side effect method for raising an AWSReportDownloaderError."""
    raise AWSReportDownloaderError()


def mock_download_file_error(manifest):
    """Mock side effect for raising an AWSReportDownloaderNoFileError."""
    raise AWSReportDownloaderNoFileError()


class FakeSession:
    """
    Fake Boto Session object.

    This is here because Moto doesn't mock out the 'cur' endpoint yet. As soon
    as Moto supports 'cur', this can be removed.
    """

    @staticmethod
    def client(service):
        """Return a fake AWS Client with a report."""
        fake_report = {
            'ReportDefinitions': [
                {
                    'ReportName': REPORT,
                    'TimeUnit': random.choice(['HOURLY', 'DAILY']),
                    'Format': random.choice(['text', 'csv']),
                    'Compression': random.choice(['ZIP', 'GZIP']),
                    'S3Bucket': BUCKET,
                    'S3Prefix': PREFIX,
                    'S3Region': REGION,
                }
            ]
        }

        if 'cur' in service:
            return Mock(**{'describe_report_definitions.return_value': fake_report})
        else:
            return Mock()


class FakeSessionNoReport:
    """
    Fake Boto Session object with no reports in the S3 bucket.

    This is here because Moto doesn't mock out the 'cur' endpoint yet. As soon
    as Moto supports 'cur', this can be removed.
    """

    @staticmethod
    def client(service):
        """Return a fake AWS Client with no report."""
        fake_report = {'ReportDefinitions': []}

        # only mock the 'cur' boto client.
        if 'cur' in service:
            return Mock(**{'describe_report_definitions.return_value': fake_report})
        else:
            return Mock()


class FakeSessionDownloadError:
    """
    Fake Boto Session object.

    This is here because Moto doesn't mock out the 'cur' endpoint yet. As soon
    as Moto supports 'cur', this can be removed.
    """

    @staticmethod
    def client(service):
        """Return a fake AWS Client with an error."""
        fake_report = {
            'ReportDefinitions': [
                {
                    'ReportName': REPORT,
                    'TimeUnit': random.choice(['HOURLY', 'DAILY']),
                    'Format': random.choice(['text', 'csv']),
                    'Compression': random.choice(['ZIP', 'GZIP']),
                    'S3Bucket': BUCKET,
                    'S3Prefix': PREFIX,
                    'S3Region': REGION,
                }
            ]
        }

        if 'cur' in service:
            return Mock(**{'describe_report_definitions.return_value': fake_report})
        elif 's3' in service:
            return Mock(**{'get_object.side_effect': mock_kwargs_error})
        else:
            return Mock()


class AWSReportDownloaderTest(MasuTestCase):
    """Test Cases for the AWS S3 functions."""

    fake = Faker()

    @classmethod
    def setUpClass(cls):
        """Set up shared class variables."""
        super().setUpClass()
        cls.fake_customer_name = CUSTOMER_NAME
        cls.fake_report_name = REPORT
        cls.fake_bucket_prefix = PREFIX
        cls.fake_bucket_name = BUCKET
        cls.selected_region = REGION
        cls.auth_credential = fake_arn(service='iam', generate_account_id=True)

        cls.manifest_accessor = ReportManifestDBAccessor()

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def setUp(self, fake_session):
        """Set up shared variables."""
        super().setUp()
        os.makedirs(DATA_DIR, exist_ok=True)
        self.mock_task = Mock(request=Mock(id=str(self.fake.uuid4()), return_value={}))

        self.report_downloader = ReportDownloader(
            task=self.mock_task,
            customer_name=self.fake_customer_name,
            access_credential=self.auth_credential,
            report_source=self.fake_bucket_name,
            provider_type=Provider.PROVIDER_AWS,
            provider_uuid=self.aws_provider_uuid,
        )
        self.aws_report_downloader = AWSReportDownloader(
            **{
                'task': self.mock_task,
                'customer_name': self.fake_customer_name,
                'auth_credential': self.auth_credential,
                'bucket': self.fake_bucket_name,
                'report_name': self.fake_report_name,
                'provider_uuid': self.aws_provider_uuid,
            }
        )

    def tearDown(self):
        """Remove test generated data."""
        shutil.rmtree(DATA_DIR, ignore_errors=True)

    @patch('masu.external.downloader.aws.aws_report_downloader.boto3.resource')
    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader.download_file',
        return_value=('mock_file_name', None),
    )
    def test_download_bucket(self, mock_boto_resource, mock_download_file):
        """Test download bucket method."""
        mock_resource = Mock()
        mock_bucket = Mock()
        mock_bucket.objects.all.return_value = []
        mock_resource.Bucket.return_value = mock_bucket
        out = self.aws_report_downloader.download_bucket()
        expected_files = []
        self.assertEqual(out, expected_files)

    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader.download_file',
        side_effect=mock_download_file_error,
    )
    def test_download_report_missing_manifest(self, mock_download_file):
        """Test download fails when manifest is missing."""
        fake_report_date = self.fake.date_time().replace(day=1)
        out = self.report_downloader.download_report(fake_report_date)
        self.assertEqual(out, [])

    @patch('masu.external.report_downloader.ReportStatsDBAccessor')
    @patch(
        'masu.util.aws.common.get_assume_role_session', return_value=FakeSessionDownloadError,
    )
    def test_download_report_missing_bucket(self, mock_stats, fake_session):
        """Test download fails when bucket is missing."""
        mock_stats.return_value.__enter__ = Mock()
        fake_report_date = self.fake.date_time().replace(day=1)
        fake_report_date_str = fake_report_date.strftime('%Y%m%dT000000.000Z')
        expected_assembly_id = '882083b7-ea62-4aab-aa6a-f0d08d65ee2b'
        input_key = f'/koku/20180701-20180801/{expected_assembly_id}/koku-1.csv.gz'
        mock_manifest = {
            'assemblyId': expected_assembly_id,
            'billingPeriod': {'start': fake_report_date_str},
            'reportKeys': [input_key],
        }

        with patch.object(AWSReportDownloader, '_get_manifest', return_value=('', mock_manifest)):
            with self.assertRaises(AWSReportDownloaderError):
                report_downloader = ReportDownloader(
                    task=self.mock_task,
                    customer_name=self.fake_customer_name,
                    access_credential=self.auth_credential,
                    report_source=self.fake_bucket_name,
                    provider_type=Provider.PROVIDER_AWS,
                    provider_uuid=self.aws_provider_uuid,
                )
                AWSReportDownloader(
                    **{
                        'task': self.mock_task,
                        'customer_name': self.fake_customer_name,
                        'auth_credential': self.auth_credential,
                        'bucket': self.fake_bucket_name,
                        'report_name': self.fake_report_name,
                        'provider_uuid': self.aws_provider_uuid,
                    }
                )
                report_downloader.download_report(fake_report_date)

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_missing_report_name(self, fake_session):
        """Test downloading a report with an invalid report name."""
        auth_credential = fake_arn(service='iam', generate_account_id=True)

        with self.assertRaises(MasuProviderError):
            AWSReportDownloader(
                self.mock_task, self.fake_customer_name, auth_credential, 's3_bucket', 'wrongreport'
            )

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_download_default_report(self, fake_session):
        """Test assume aws role works."""
        # actual test
        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        self.assertEqual(downloader.report_name, self.fake_report_name)

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSessionNoReport)
    @patch('masu.util.aws.common.get_cur_report_definitions', return_value=[])
    def test_download_default_report_no_report_found(self, fake_session, fake_report_list):
        """Test download fails when no reports are found."""
        auth_credential = fake_arn(service='iam', generate_account_id=True)

        with self.assertRaises(MasuProviderError):
            AWSReportDownloader(
                self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
            )

    @patch('masu.external.downloader.aws.aws_report_downloader.shutil')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_check_size_success(self, fake_session, fake_shutil):
        """Test _check_size is successful."""
        fake_client = Mock()
        fake_client.get_object.return_value = {'ContentLength': 123456, 'Body': Mock()}
        fake_shutil.disk_usage.return_value = (10, 10, 4096 * 1024 * 1024)

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(
            depth=random.randint(1, 5), extension=random.choice(['json', 'csv.gz'])
        )
        result = downloader._check_size(fakekey, check_inflate=False)
        self.assertTrue(result)

    @patch('masu.external.downloader.aws.aws_report_downloader.shutil')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_check_size_fail_nospace(self, fake_session, fake_shutil):
        """Test _check_size fails if there is no more space."""
        fake_client = Mock()
        fake_client.get_object.return_value = {'ContentLength': 123456, 'Body': Mock()}
        fake_shutil.disk_usage.return_value = (10, 10, 10)

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(
            depth=random.randint(1, 5), extension=random.choice(['json', 'csv.gz'])
        )
        result = downloader._check_size(fakekey, check_inflate=False)
        self.assertFalse(result)

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_check_size_fail_nosize(self, fake_session):
        """Test _check_size fails if there report has no size."""
        fake_client = Mock()
        fake_client.get_object.return_value = {}

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(
            depth=random.randint(1, 5), extension=random.choice(['json', 'csv.gz'])
        )
        with self.assertRaises(AWSReportDownloaderError):
            downloader._check_size(fakekey, check_inflate=False)

    @patch('masu.external.downloader.aws.aws_report_downloader.shutil')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_check_size_inflate_success(self, fake_session, fake_shutil):
        """Test _check_size inflation succeeds."""
        fake_client = Mock()
        fake_client.get_object.return_value = {
            'ContentLength': 123456,
            'Body': io.BytesIO(b'\xd2\x02\x96I'),
        }
        fake_shutil.disk_usage.return_value = (10, 10, 4096 * 1024 * 1024)

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(depth=random.randint(1, 5), extension='csv.gz')
        result = downloader._check_size(fakekey, check_inflate=True)
        self.assertTrue(result)

    @patch('masu.external.downloader.aws.aws_report_downloader.shutil')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_check_size_inflate_fail(self, fake_session, fake_shutil):
        """Test _check_size fails when inflation fails."""
        fake_client = Mock()
        fake_client.get_object.return_value = {
            'ContentLength': 123456,
            'Body': io.BytesIO(b'\xd2\x02\x96I'),
        }
        fake_shutil.disk_usage.return_value = (10, 10, 1234567)

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(depth=random.randint(1, 5), extension='csv.gz')
        result = downloader._check_size(fakekey, check_inflate=True)
        self.assertFalse(result)

    @patch('masu.external.downloader.aws.aws_report_downloader.shutil')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_download_file_check_size_fail(self, fake_session, fake_shutil):
        """Test _check_size fails when key is fake."""
        fake_client = Mock()
        fake_client.get_object.return_value = {
            'ContentLength': 123456,
            'Body': io.BytesIO(b'\xd2\x02\x96I'),
        }
        fake_shutil.disk_usage.return_value = (10, 10, 1234567)

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        fakekey = self.fake.file_path(depth=random.randint(1, 5), extension='csv.gz')
        with self.assertRaises(AWSReportDownloaderError):
            downloader.download_file(fakekey)

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_download_file_raise_downloader_err(self, fake_session):
        """Test _check_size fails when there is a downloader error."""
        fake_response = {'Error': {'Code': self.fake.word()}}
        fake_client = Mock()
        fake_client.get_object.side_effect = ClientError(fake_response, 'masu-test')

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        with self.assertRaises(AWSReportDownloaderError):
            downloader.download_file(self.fake.file_path())

    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_download_file_raise_nofile_err(self, fake_session):
        """Test that downloading a nonexistent file fails with AWSReportDownloaderNoFileError."""
        fake_response = {'Error': {'Code': 'NoSuchKey'}}
        fake_client = Mock()
        fake_client.get_object.side_effect = ClientError(fake_response, 'masu-test')

        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )
        downloader.s3_client = fake_client

        with self.assertRaises(AWSReportDownloaderNoFileError):
            downloader.download_file(self.fake.file_path())

    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader.check_if_manifest_should_be_downloaded'
    )
    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader._remove_manifest_file'
    )
    @patch('masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader._get_manifest')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_get_report_context_for_date_should_download(
        self, mock_session, mock_manifest, mock_delete, mock_check
    ):
        """Test that data is returned on the reports to process."""
        current_month = DateAccessor().today().replace(day=1, second=1, microsecond=1)
        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task,
            self.fake_customer_name,
            auth_credential,
            self.fake_bucket_name,
            provider_uuid=self.aws_provider_uuid,
        )

        start_str = current_month.strftime(downloader.manifest_date_format)
        assembly_id = '1234'
        compression = downloader.report.get('Compression')
        report_keys = ['file1', 'file2']
        mock_manifest.return_value = (
            '',
            {
                'assemblyId': assembly_id,
                'Compression': compression,
                'reportKeys': report_keys,
                'billingPeriod': {'start': start_str},
            },
        )
        mock_check.return_value = True

        expected = {
            'manifest_id': None,
            'assembly_id': assembly_id,
            'compression': compression,
            'files': report_keys,
        }

        result = downloader.get_report_context_for_date(current_month)
        with ReportManifestDBAccessor() as manifest_accessor:
            manifest_entry = manifest_accessor.get_manifest(assembly_id, self.aws_provider_uuid)
            expected['manifest_id'] = manifest_entry.id

        self.assertIsInstance(result, dict)
        for key, value in result.items():
            self.assertIn(key, expected)
            self.assertEqual(value, expected.get(key))

    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader.check_if_manifest_should_be_downloaded'
    )
    @patch(
        'masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader._remove_manifest_file'
    )
    @patch('masu.external.downloader.aws.aws_report_downloader.AWSReportDownloader._get_manifest')
    @patch('masu.util.aws.common.get_assume_role_session', return_value=FakeSession)
    def test_get_report_context_for_date_should_not_download(
        self, mock_session, mock_manifest, mock_delete, mock_check
    ):
        """Test that no data is returned when we don't want to process."""
        current_month = DateAccessor().today().replace(day=1, second=1, microsecond=1)
        auth_credential = fake_arn(service='iam', generate_account_id=True)
        downloader = AWSReportDownloader(
            self.mock_task, self.fake_customer_name, auth_credential, self.fake_bucket_name
        )

        start_str = current_month.strftime(downloader.manifest_date_format)
        assembly_id = '1234'
        compression = downloader.report.get('Compression')
        report_keys = ['file1', 'file2']
        mock_manifest.return_value = (
            '',
            {
                'assemblyId': assembly_id,
                'Compression': compression,
                'reportKeys': report_keys,
                'billingPeriod': {'start': start_str},
            },
        )
        mock_check.return_value = False

        expected = {}

        result = downloader.get_report_context_for_date(current_month)
        self.assertEqual(result, expected)

    def test_remove_manifest_file(self):
        """Test that we remove the manifest file."""
        manifest_file = f'{DATA_DIR}/test_manifest.json'

        with open(manifest_file, 'w') as f:
            f.write('Test')

        self.assertTrue(os.path.isfile(manifest_file))
        self.aws_report_downloader._remove_manifest_file(manifest_file)
        self.assertFalse(os.path.isfile(manifest_file))

    def test_delete_manifest_file_warning(self):
        """Test that an INFO is logged when removing a manifest file that does not exist."""
        with self.assertLogs(logger='masu.external.downloader.aws.aws_report_downloader',
                             level='INFO') as captured_logs:
            # Disable log suppression
            logging.disable(logging.NOTSET)
            self.aws_report_downloader._remove_manifest_file('None')
            self.assertTrue(captured_logs.output[0].startswith('INFO:'),
                            msg="The log is expected to start with 'INFO:' but instead was: "
                            + captured_logs.output[0])
            self.assertTrue('Could not delete manifest file at' in captured_logs.output[0],
                            msg="""The log message is expected to contain
                                   'Could not delete manifest file at' but instead was: """
                            + captured_logs.output[0])
            # Re-enable log suppression
            logging.disable(logging.CRITICAL)
