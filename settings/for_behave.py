"""Settings for running the BDD suite under ``features/`` via ``manage.py behave``.

Kept separate from ``with_sqlite3`` (used by ``manage.py test``) so that the
BDD-specific dependency (``behave_django``) isn't a hard requirement just to
run the regular Django test suite.
"""

from .with_sqlite3 import *  # noqa: F401,F403

INSTALLED_APPS += (
    'behave_django',
)
