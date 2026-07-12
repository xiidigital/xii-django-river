import logging

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import PROTECT
from django.utils.translation import gettext_lazy as _

from river.config import app_config
from django.contrib.contenttypes.fields import GenericForeignKey

from river.models import Workflow, BaseModel
from river.models.function import Function

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
                    "(river.approve_function / river.self_approve_function) "
                    "before wiring it into a workflow hook."
                )}
            )

    def execute(self, context):
        try:
            self.callback_function.get()(context)
        except Exception as e:
            if app_config.STRICT_HOOKS:
                raise
            LOGGER.exception(e)
