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
        checks.register(check_hooks_with_unapproved_functions, checks.Tags.database)
        checks.register(check_timeout_with_offthread_executor, checks.Tags.compatibility)

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


def check_hooks_with_unapproved_functions(app_configs, **kwargs):
    """
    Hook.save() (xii/django_river/models/hook.py) only validates that its
    callback_function is approved at the moment the Hook itself is saved.
    Editing that Function's body afterwards resets is_approved to False
    (Function's on_pre_save) without touching any Hook that already points
    to it - the Hook row is left in place, silently pointing at code that
    is no longer approved to run. Hook.execute() -> Function.get() does
    still refuse to run it (raises ImproperlyConfigured), but nothing
    surfaces that fact until the hook actually fires and someone is
    watching logs (or RIVER_STRICT_HOOKS is on and it blocks a transition).
    This check makes that misconfiguration visible ahead of time instead.
    """
    from xii.django_river.models import OnApprovedHook, OnTransitHook, OnCompleteHook

    warnings = []
    try:
        for hook_model in (OnApprovedHook, OnTransitHook, OnCompleteHook):
            unapproved = hook_model.objects.filter(
                callback_function__is_approved=False
            ).select_related('callback_function', 'workflow')
            for hook in unapproved:
                warnings.append(checks.Warning(
                    "%s #%s in workflow '%s' points at function '%s', which is not "
                    "approved. Hook.execute() will refuse to run it "
                    "(ImproperlyConfigured) until the function is approved again." % (
                        hook_model.__name__, hook.pk, hook.workflow, hook.callback_function),
                    obj=hook,
                    id='xii_django_river.W005',
                ))
    except (OperationalError, ProgrammingError):
        pass
    return warnings


def check_timeout_with_offthread_executor(app_configs, **kwargs):
    """
    RIVER_FUNCTION_TIMEOUT_SECONDS (xii/django_river/timeout.py) is enforced
    with signal.alarm, which only works in the main thread of the main
    interpreter. RIVER_HOOK_EXECUTOR set to anything other than the
    synchronous default (unset) moves Hook.execute_now() off that thread -
    the built-in thread_pool_executor documents this explicitly in its own
    docstring (xii/django_river/executors.py), but a custom executor
    pointing at Celery/RQ/etc. has the identical problem and nothing
    connects the two settings for someone configuring them independently.
    This is a settings-only check (no DB access), so it runs under
    Tags.compatibility rather than Tags.database like the others here.
    """
    from xii.django_river.config import app_config

    warnings = []
    if app_config.FUNCTION_TIMEOUT_SECONDS and app_config.HOOK_EXECUTOR:
        warnings.append(checks.Warning(
            "RIVER_FUNCTION_TIMEOUT_SECONDS is set together with RIVER_HOOK_EXECUTOR "
            "('%s'). The timeout is enforced with signal.alarm, which only works on "
            "the main thread of the main interpreter - once RIVER_HOOK_EXECUTOR moves "
            "hook execution off that thread (or out of process), the timeout silently "
            "stops applying. A hung Function body will hang the executor's own "
            "thread/worker instead of being cut off." % app_config.HOOK_EXECUTOR,
            obj='xii_django_river',
            id='xii_django_river.W006',
        ))
    return warnings
