import os
import shutil
from datetime import datetime, timedelta

import pytz
from celery import shared_task
from django.conf import settings
from django.utils import timezone
import logging


@shared_task
def cleanup_tmp_folder():
    threshold = timezone.now() - timedelta(days=settings.CLEAN_UP_OLD_FILES_DAYS_THRESHOLD)

    for file in settings.TMP_DIR.iterdir():
       if datetime.fromtimestamp(file.stat().st_mtime, tz=pytz.timezone(settings.TIME_ZONE)) < threshold:
           logging.info('Delete file %s', file)
           if file.is_dir():
               shutil.rmtree(file)
           else:
               os.unlink(file)
