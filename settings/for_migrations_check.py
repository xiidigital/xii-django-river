"""Settings used only by CI's "makemigrations --check" step.

``with_sqlite3`` (and the other ``with_*`` settings modules) set
``MIGRATION_MODULES = DisableMigrations()`` so the test suite can build the
schema directly instead of replaying migrations, which is fine for running
tests but means Django believes *no* app has any migrations at all -
``makemigrations --check`` can't tell whether ``xii_django_river`` is
missing a migration when it's told to disregard every migrations module in
the project. This settings module is identical to ``with_sqlite3`` except it
leaves ``MIGRATION_MODULES`` unset, so the check reflects the real migration
state on disk.
"""

from .base import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    },
}

INSTALLED_APPS += (
    'xii.django_river.tests',
)
