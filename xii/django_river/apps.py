import logging
import operator
from functools import reduce

from django.apps import AppConfig
from django.core import checks
from django.db.utils import OperationalError, ProgrammingError

LOGGER = logging.getLogger(__name__)


class RiverApp(AppConfig):
    name = 'xii.django_river'
    label = 'xii_django_river'
    default_auto_field = 'django.db.models.AutoField'

    def ready(self):
        checks.register(check_workflow_definitions, checks.Tags.database)

        from xii.django_river.config import app_config

        if app_config.INJECT_MODEL_ADMIN:
            for model_class in self._get_all_workflow_classes():
                self._register_hook_inlines(model_class)

        LOGGER.debug('RiverApp is loaded.')

    @classmethod
    def _get_all_workflow_fields(cls):
        from xii.django_river.core.workflowregistry import workflow_registry
        return reduce(operator.concat, map(list, workflow_registry.workflows.values()), [])

    @classmethod
    def _get_all_workflow_classes(cls):
        from xii.django_river.core.workflowregistry import workflow_registry
        return workflow_registry.registered_classes

    @classmethod
    def _get_workflow_class_fields(cls, model):
        from xii.django_river.core.workflowregistry import workflow_registry
        return workflow_registry.get_class_fields(model)

    def _register_hook_inlines(self, model):  # pylint: disable=no-self-use
        from django.contrib import admin
        from xii.django_river.core.workflowregistry import workflow_registry
        from xii.django_river.admin import OnApprovedHookInline, OnTransitHookInline, OnCompleteHookInline, DefaultWorkflowModelAdmin

        registered_admin = admin.site._registry.get(model, None)
        if registered_admin:
            if OnApprovedHookInline not in registered_admin.inlines:
                registered_admin.inlines = list(set(list(registered_admin.inlines) + [OnApprovedHookInline, OnTransitHookInline, OnCompleteHookInline]))
                registered_admin.readonly_fields = list(set(list(registered_admin.readonly_fields) + list(workflow_registry.get_class_fields(model))))
                admin.site._registry[model] = registered_admin
        else:
            admin.site.register(model, DefaultWorkflowModelAdmin)


def check_workflow_definitions(app_configs, **kwargs):
    from xii.django_river.models import Workflow

    warnings = []
    try:
        for field_name in RiverApp._get_all_workflow_fields():
            if not Workflow.objects.filter(field_name=field_name).exists():
                warnings.append(checks.Warning(
                    "%s field doesn't seem to have any workflow defined in the database. "
                    "You should create its workflow." % field_name,
                    obj='xii_django_river',
                    id='xii_django_river.W001',
                ))
    except (OperationalError, ProgrammingError):
        pass
    return warnings
