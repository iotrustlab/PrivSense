"""Portable local inputs and safe paths for reports intended for publication."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = 'data/source/UTAH-STM-HAR'


def dataset_path(configured=None):
    """Resolve an environment override or a checkout-relative dataset location."""
    load_dotenv(ROOT / '.env')
    location = os.environ.get('PRIVSENSE_DATASET') or configured or DEFAULT_DATASET
    return (ROOT / Path(location).expanduser()).resolve()


def public_path(path):
    """Keep published artifacts free of usernames and machine directory layouts."""
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return f'<local>/{path.name}'
