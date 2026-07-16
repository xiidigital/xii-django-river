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
        checks.register(check_workflow_configuration, checks.Tags.database)

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
                # dict.fromkeys(...) dedupes while preserving insertion
                # order - unlike the set() this replaced, which reshuffles
                # column/inline order on every process restart (Python's
                # hash randomization salts str/class hashing per-process),
                # producing a different-looking admin on every deploy for
                # no functional reason.
                registered_admin.inlines = list(dict.fromkeys(
                    list(registered_admin.inlines) + [OnApprovedHookInline, OnTransitHookInline, OnCompleteHookInline]
                ))
                registered_admin.readonly_fields = list(dict.fromkeys(
                    list(registered_admin.readonly_fields) + list(workflow_registry.get_class_fields(model))
                ))
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


def check_workflow_configuration(app_configs, **kwargs):
    """
    Configuration lint, not correctness: these are cases that run without
    raising, but almost certainly aren't what whoever set up the workflow
    meant. Every one of these was only discoverable in the admin, row by
    row, before this existed.
    """
    from xii.django_river.models import State, TransitionMeta, TransitionApprovalMeta, Workflow

    warnings = []
    try:
        # A transition with zero TransitionApprovalMeta rows - or one whose
        # rows all lack both permissions and groups - has nothing for
        # OrmDriver._authorized_approvals() to check: `Q(permissions__isnull=True)
        # | ...` and `Q(groups__isnull=True) | ...` are both vacuously true,
        # so *any authenticated user* can approve it as-is. That's sometimes
        # intentional (an open step in a workflow), but silent
        # misconfiguration is the more common reason, so it's worth flagging.
        metas_without_rules = TransitionMeta.objects.filter(
            transition_approval_meta__isnull=True
        ).select_related('workflow', 'source_state', 'destination_state').distinct()
        for meta in metas_without_rules:
            warnings.append(checks.Warning(
                "Transition '%s' -> '%s' in workflow '%s' has no authorization rule "
                "at all (no TransitionApprovalMeta). As configured, any authenticated "
                "user can approve it - see OrmDriver._authorized_approvals()." % (
                    meta.source_state, meta.destination_state, meta.workflow),
                obj=meta,
                id='xii_django_river.W002',
            ))

        open_rules = TransitionApprovalMeta.objects.filter(
            permissions__isnull=True, groups__isnull=True
        ).select_related(
            'workflow', 'transition_meta__source_state', 'transition_meta__destination_state'
        ).distinct()
        for rule in open_rules:
            warnings.append(checks.Warning(
                "The priority-%s authorization rule for transition '%s' -> '%s' in "
                "workflow '%s' has neither permissions nor groups. As configured, any "
                "authenticated user satisfies it." % (
                    rule.priority, rule.transition_meta.source_state,
                    rule.transition_meta.destination_state, rule.workflow),
                obj=rule,
                id='xii_django_river.W003',
            ))

        # A State that is nobody's initial_state and appears in no
        # TransitionMeta at all is unreachable and leads nowhere - almost
        # always a leftover from renaming/restructuring a workflow rather
        # than something intentional.
        used_state_ids = (
            set(TransitionMeta.objects.values_list('source_state_id', flat=True)) |
            set(TransitionMeta.objects.values_list('destination_state_id', flat=True)) |
            set(Workflow.objects.values_list('initial_state_id', flat=True))
        )
        for state in State.objects.exclude(pk__in=used_state_ids):
            warnings.append(checks.Warning(
                "State '%s' is not used as the source or destination of any transition, "
                "nor as any workflow's initial state." % state.label,
                obj=state,
                id='xii_django_river.W004',
            ))
    except (OperationalError, ProgrammingError):
        pass
    return warnings
