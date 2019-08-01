"""Celery configuration for the Koku project."""
import logging
import os
import datetime

import django
from django.apps import apps
from django.conf import settings
from celery import Celery
from celery.schedules import crontab
from celery.signals import after_setup_logger
from .env import ENVIRONMENT


LOGGER = logging.getLogger(__name__)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koku.settings')

LOGGER.info('Starting celery.')
# Django setup is required *before* Celery app can start correctly.
django.setup()
LOGGER.info('Django setup.')

APP = Celery('koku', broker=django.conf.settings.CELERY_BROKER_URL)
APP.config_from_object('django.conf:settings', namespace='CELERY')

LOGGER.info('Celery autodiscover tasks.')

if ENVIRONMENT.bool('SCHEDULE_REPORT_CHECKS', default=False):
    # The interval to scan for new reports.
    REPORT_CHECK_INTERVAL = datetime.timedelta(
        minutes=int(os.getenv('SCHEDULE_CHECK_INTERVAL', '60')))

    check_report_updates_def = {'task': 'masu.celery.tasks.check_report_updates',
                                'schedule': REPORT_CHECK_INTERVAL.seconds,
                                'args': []}
    APP.conf.beat_schedule['check-report-updates'] = check_report_updates_def


# Specify the day of the month for removal of expired report data.
REMOVE_EXPIRED_REPORT_DATA_ON_DAY = int(ENVIRONMENT.get_value('REMOVE_EXPIRED_REPORT_DATA_ON_DAY', default='1'))

# Specify the time of the day for removal of expired report data.
REMOVE_EXPIRED_REPORT_UTC_TIME = ENVIRONMENT.get_value('REMOVE_EXPIRED_REPORT_UTC_TIME', default='00:00')

if REMOVE_EXPIRED_REPORT_DATA_ON_DAY != 0:
    cleaning_day = REMOVE_EXPIRED_REPORT_DATA_ON_DAY
    cleaning_time = REMOVE_EXPIRED_REPORT_UTC_TIME
    hour, minute = cleaning_time.split(':')

    remove_expired_data_def = {'task': 'masu.celery.tasks.remove_expired_data',
                                'schedule': crontab(hour=int(hour),
                                                    minute=int(minute),
                                                    day_of_month=cleaning_day),
                                'args': []}
    APP.conf.beat_schedule['remove-expired-data'] = remove_expired_data_def

APP.autodiscover_tasks()

# The signal decorator is associated with the
# following method signature, but args and kwargs are not currently utilized.
# Learn more about celery signals here:
# http://docs.celeryproject.org/en/v4.2.0/userguide/signals.html#logging-signals
@after_setup_logger.connect
def setup_loggers(logger, *args, **kwargs):  # pylint: disable=unused-argument
    """Add logging for celery with optional cloud watch."""
    return  #TODO this is causing double logging in the worker
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
