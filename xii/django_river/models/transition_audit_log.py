from django.conf import settings
from django.db import models
from django.db.models import PROTECT, SET_NULL
from django.utils.translation import gettext_lazy as _

from xii.django_river.config import app_config
from xii.django_river.models.base_model import BaseModel
from xii.django_river.models.state import State
from xii.django_river.models.workflow import Workflow


class TransitionAuditLog(BaseModel):
    """
    Immutable, append-only record of every state-changing event on a
    workflow object: who did it (when there is a "who"), and when.

    Why this exists alongside ``TransitionApproval``: that model already
    carries ``transactioner``/``transaction_date`` for the APPROVED path,
    but rows there are mutated in place (PENDING -> APPROVED/CANCELLED/
    JUMPED) rather than appended to, and the CANCELLED/JUMPED paths
    (``InstanceWorkflowObject.cancel_impossible_future`` /``.jump_to``) never
    recorded who triggered them or when - only the resulting status. This
    model is written once per event and never updated or deleted from
    application code, so "what actually happened, in what order, by whom"
    survives even if the live approval rows are later changed again.

    Rows are created from ``InstanceWorkflowObject`` (approve /
    cancel_impossible_future / jump_to), not here - this module only defines
    the shape.
    """

    ACTION_APPROVED = "APPROVED"
    ACTION_CANCELLED = "CANCELLED"
    ACTION_JUMPED = "JUMPED"
    ACTION_CHOICES = [
        (ACTION_APPROVED, _("Approved")),
        (ACTION_CANCELLED, _("Cancelled")),
        (ACTION_JUMPED, _("Jumped")),
    ]

    workflow = models.ForeignKey(Workflow, verbose_name=_("Workflow"), related_name="audit_logs", on_delete=PROTECT)

    content_type = models.ForeignKey(app_config.CONTENT_TYPE_CLASS, verbose_name=_("Content Type"), on_delete=PROTECT)
    object_id = models.CharField(verbose_name=_("Related Object"), max_length=200)

    source_state = models.ForeignKey(State, verbose_name=_("Source State"), related_name="+", on_delete=PROTECT)
    destination_state = models.ForeignKey(State, verbose_name=_("Destination State"), related_name="+", on_delete=PROTECT)

    # Nullable/SET_NULL on purpose: an audit trail must never be the reason
    # a Transition can't be deleted, and never lose its own history if one
    # ever is. source_state/destination_state above are denormalized so the
    # row stays meaningful even if transition becomes NULL.
    transition = models.ForeignKey(
        "xii_django_river.Transition", verbose_name=_("Transition"), related_name="audit_logs",
        null=True, blank=True, on_delete=SET_NULL,
    )

    action = models.CharField(verbose_name=_("Action"), max_length=20, choices=ACTION_CHOICES)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Actor"), related_name="+",
        null=True, blank=True, on_delete=SET_NULL,
    )
    # Same reasoning as FunctionRevision.changed_by_username: actor is
    # SET_NULL, so "who did this" needs to survive the account being deleted
    # later, not just while it still exists.
    actor_username = models.CharField(verbose_name=_("Actor (snapshot)"), max_length=150, blank=True)

    class Meta:
        app_label = "xii_django_river"
        verbose_name = _("Transition Audit Log")
        verbose_name_plural = _("Transition Audit Logs")
        ordering = ["-date_created"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return "%s: %s -> %s (%s)" % (self.workflow, self.source_state, self.destination_state, self.action)


def username_snapshot(user):
    if user is None:
        return ""
    get_username = getattr(user, "get_username", None)
    return get_username() if callable(get_username) else str(user)
