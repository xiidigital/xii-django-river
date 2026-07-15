from uuid import uuid4

from .base import *

DB_HOST = os.environ['POSTGRES_HOST']
DB_PORT = os.environ['POSTGRES_5432_TCP_PORT']
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'river',
        'USER': 'river',
        'PASSWORD': 'river',
        'HOST': DB_HOST,
        'PORT': DB_PORT,
        'TEST': {
            'NAME': 'river' + str(uuid4()),

        },
    }
}

INSTALLED_APPS += (
    'xii.django_river.tests',
)

MIGRATION_MODULES = DisableMigrations()
