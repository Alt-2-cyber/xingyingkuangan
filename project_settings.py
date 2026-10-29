"""Read deployment settings from the process environment or a local JSON file."""

import json
import os
from pathlib import Path


LOCAL_FILE = Path(__file__).resolve().with_name('settings.local.json')
_local = json.loads(LOCAL_FILE.read_text(encoding='utf-8')) if LOCAL_FILE.exists() else {}


def setting(name, default=''):
    return os.environ.get(name, _local.get(name, default))
