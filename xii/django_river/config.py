from django.contrib.auth.models import Permission, Group
from django.contrib.contenttypes.models import ContentType
from django.db import connection


class RiverConfig(object):
    """
    Lee la configuración de Django en cada acceso, de modo que
    ``override_settings`` y los cambios dinámicos se respetan.
    """

    prefix = 'RIVER'

    def _defaults(self):
        from django.conf import settings
        return {
            'CONTENT_TYPE_CLASS': ContentType,
            'USER_CLASS': settings.AUTH_USER_MODEL,
            'PERMISSION_CLASS': Permission,
            'GROUP_CLASS': Group,
            'INJECT_MODEL_ADMIN': False,
            'STRICT_HOOKS': False,
            'ALLOW_DB_FUNCTIONS': False,
            'SANDBOX_DB_FUNCTIONS': False,
            'FUNCTION_TIMEOUT_SECONDS': None,
            'HOOK_EXECUTOR': None,
        }

    def get_with_prefix(self, config):
        return '%s_%s' % (self.prefix, config)

    def __getattr__(self, item):
        if item == 'IS_MSSQL':
            return connection.vendor == 'microsoft'
        defaults = self._defaults()
        if item in defaults:
            from django.conf import settings
            return getattr(settings, self.get_with_prefix(item), defaults[item])
        raise AttributeError(item)


app_config = RiverConfig()
