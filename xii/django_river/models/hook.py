import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import PROTECT
from django.utils.translation import gettext_lazy as _

from xii.django_river.config import app_config
from django.contrib.contenttypes.fields import GenericForeignKey

from xii.django_river.models import Workflow, BaseModel
from xii.django_river.models.function import Function

BEFORE = "BEFORE"
AFTER = "AFTER"

HOOK_TYPES = [
    (BEFORE, _('Before')),
    (AFTER, _('After')),
]

LOGGER = logging.getLogger(__name__)


class Hook(BaseModel):
    class Meta:
        abstract = True

    callback_function = models.ForeignKey(Function, verbose_name=_("Function"), related_name='%(app_label)s_%(class)s_hooks', on_delete=PROTECT)
    workflow = models.ForeignKey(Workflow, verbose_name=_("Workflow"), related_name='%(app_label)s_%(class)s_hooks', on_delete=PROTECT)

    content_type = models.ForeignKey(ContentType, blank=True, null=True, on_delete=models.SET_NULL)
    object_id = models.CharField(max_length=200, blank=True, null=True)
    workflow_object = GenericForeignKey('content_type', 'object_id')

    hook_type = models.CharField(_('When?'), choices=HOOK_TYPES, max_length=50)

    def clean(self):
        super().clean()
        self._validate_callback_function_is_approved()

    def save(self, *args, **kwargs):
        # Reject at configuration time, not at execution time: a Hook
        # wired to an unapproved Function would otherwise fail silently
        # at runtime (see Hook.execute / RIVER_STRICT_HOOKS), which hides
        # a misconfiguration behind "nothing happened". Enforced in save()
        # (not just clean()) so this holds regardless of entry point —
        # admin, a data migration, or plain ORM code.
        self._validate_callback_function_is_approved()
        super().save(*args, **kwargs)

    def _validate_callback_function_is_approved(self):
        if self.callback_function_id and not self.callback_function.is_approved:
            raise ValidationError(
                {"callback_function": _(
                    "This Function hasn't been approved yet. Approve it "
                    "(xii_django_river.approve_function / xii_django_river.self_approve_function) "
                    "before wiring it into a workflow hook."
                )}
            )

    def execute(self, context):
        """
        Entry point used by the signal handlers (xii/django_river/signals.py).
        Dispatches to RIVER_HOOK_EXECUTOR if one is configured (see
        xii/django_river/executors.py); otherwise runs synchronously, inline,
        exactly as before that setting existed.
        """
        executor = app_config.HOOK_EXECUTOR
        if executor:
            from django.utils.module_loading import import_string
            import_string(executor)(self, context)
            return
        self.execute_now(context)

    def execute_now(self, context):
        """
        The actual, synchronous execution of this hook's callback function.
        Public (not prefixed with `_`) because a custom RIVER_HOOK_EXECUTOR
        - e.g. one that re-dispatches through Celery - calls back into this
        from inside its own worker, after rebuilding an equivalent context.
        """
        try:
            # RIVER_FUNCTION_TIMEOUT_SECONDS is enforced inside
            # Function.get() itself (xii/django_river/models/function.py),
            # so it applies uniformly regardless of caller.
            self.callback_function.get()(context)
        except Exception as e:
            if app_config.STRICT_HOOKS:
                raise
            LOGGER.exception(e)
