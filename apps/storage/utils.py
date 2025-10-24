from pathlib import Path
import uuid
from django.conf import settings
import shutil

def move_to_tmp_dir(file:Path, random_filename=True) -> Path:
    dst = f'{file.name}-{uuid.uuid4()}' if random_filename else file.name
    dst = settings.TMP_DIR / dst
    shutil.move(file, dst)
    return dst
