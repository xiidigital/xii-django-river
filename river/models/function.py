import difflib
import inspect
import re

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, models
from django.db.models.signals import post_save, pre_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from river.config import app_config
from river.models import BaseModel

loaded_functions = {}


class Function(BaseModel):
    name = models.CharField(verbose_name=_("Function Name"), max_length=200, unique=True, null=False, blank=False)
    body = models.TextField(verbose_name=_("Function Body"), max_length=100000, null=False, blank=False)
    version = models.IntegerField(verbose_name=_("Function Version"), default=0)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Created By"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Last Updated By"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    is_approved = models.BooleanField(verbose_name=_("Approved"), default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Approved By"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    approved_at = models.DateTimeField(verbose_name=_("Approved At"), null=True, blank=True)

    class Meta:
        permissions = [
            ("approve_function", "Can approve river functions for execution"),
            ("self_approve_function", "Can approve river functions authored by oneself"),
        ]

    def __str__(self):
        return "%s - %s" % (self.name, "v%s" % self.version)

    def get(self):
        if not app_config.ALLOW_DB_FUNCTIONS:
            raise ImproperlyConfigured(
                "river.Function executes Python code stored in the database. "
                "Set RIVER_ALLOW_DB_FUNCTIONS = True to acknowledge and enable it."
            )
        if not self.is_approved:
            raise ImproperlyConfigured(
                "river.Function '%s' has not been approved for execution. "
                "A reviewer other than the author must approve it first." % self.name
            )
        cache_key = self._cache_key()
        func = loaded_functions.get(cache_key, None)
        if not func or func["version"] != self.version or func["body"] != self.body:
            func = {"function": self._load(), "version": self.version, "body": self.body}
            loaded_functions[cache_key] = func
        return func["function"]

    def _cache_key(self):
        # Under schema-per-tenant multitenancy (django-tenants), each tenant
        # has its own Function table starting its own PK sequence from 1.
        # Without the schema in the key, Tenant B could hit the process-wide
        # cache with a stale compiled function belonging to Tenant A's
        # Function #1 (or vice versa) — a cross-tenant execution bug, not
        # just a cache-miss inefficiency.
        schema = getattr(connection, "schema_name", None) or "default"
        return (schema, self.pk)

    def approve(self, approver, allow_self_approval=False):
        is_self_approval = bool(self.updated_by_id and approver.pk == self.updated_by_id)
        if is_self_approval and not allow_self_approval:
            raise ImproperlyConfigured(
                "The author of a river.Function cannot approve their own changes "
                "without the river.self_approve_function permission."
            )
        self.is_approved = True
        self.approved_by = approver
        self.approved_at = timezone.now()
        self.save(update_fields=["is_approved", "approved_by", "approved_at"])
        FunctionRevision.objects.create(
            function=self,
            version=self.version,
            action=FunctionRevision.ACTION_SELF_APPROVED if is_self_approval else FunctionRevision.ACTION_APPROVED,
            body=self.body,
            diff="",
            changed_by=approver,
            changed_by_username=_username_snapshot(approver),
        )

    def _load(self):
        if app_config.SANDBOX_DB_FUNCTIONS:
            from river.sandbox import compile_sandboxed_handle
            return compile_sandboxed_handle(self.body)

        func_body = "def _wrapper(context):\n"
        for line in self.body.split("\n"):
            func_body += "\t" + line + "\n"
        func_body += "\thandle(context)\n"
        exec(func_body)
        return eval("_wrapper")


class FunctionRevision(BaseModel):
    """
    Immutable audit trail: one row per creation/edit of a Function's body.
    Kept even if the parent Function is later deleted-and-recreated, so
    reviewers can always see the history of what was ever stored and run.
    """

    ACTION_CREATED = "CREATED"
    ACTION_UPDATED = "UPDATED"
    ACTION_APPROVED = "APPROVED"
    ACTION_SELF_APPROVED = "SELF_APPROVED"
    ACTION_CHOICES = [
        (ACTION_CREATED, _("Created")),
        (ACTION_UPDATED, _("Updated")),
        (ACTION_APPROVED, _("Approved")),
        (ACTION_SELF_APPROVED, _("Self-approved")),
    ]

    function = models.ForeignKey(Function, verbose_name=_("Function"), related_name="revisions", on_delete=models.CASCADE)
    version = models.IntegerField(verbose_name=_("Version"))
    action = models.CharField(verbose_name=_("Action"), max_length=20, choices=ACTION_CHOICES)
    body = models.TextField(verbose_name=_("Body Snapshot"), max_length=100000)
    diff = models.TextField(verbose_name=_("Diff vs Previous Version"), blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Changed By"),
        related_name="+",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    # Denormalized on purpose: changed_by is SET_NULL, so if the account is
    # later deleted the FK alone would leave this row anonymous. The audit
    # trail's whole point is answering "who did this" — that should survive
    # account deletion, so a plain-text snapshot is taken at write time.
    changed_by_username = models.CharField(verbose_name=_("Changed By (snapshot)"), max_length=150, blank=True)

    class Meta:
        ordering = ["-version"]

    def __str__(self):
        return "%s v%s (%s)" % (self.function.name, self.version, self.action)


def _username_snapshot(user):
    if user is None:
        return ""
    get_username = getattr(user, "get_username", None)
    return get_username() if callable(get_username) else str(user)


def _diff(previous_body, new_body):
    return "\n".join(
        difflib.unified_diff(
            (previous_body or "").splitlines(),
            (new_body or "").splitlines(),
            fromfile="previous",
            tofile="new",
            lineterm="",
        )
    )


def on_pre_save(sender, instance, *args, **kwargs):
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        previous = None

    instance._river_previous_body = previous.body if previous else None
    instance._river_body_changed = previous is None or previous.body != instance.body

    if instance._river_body_changed:
        instance.version += 1
        if previous is not None:
            # Any change to the body invalidates the previous approval:
            # a reviewer must sign off on the new code, not the old one.
            instance.is_approved = False
            instance.approved_by = None
            instance.approved_at = None


def on_post_save(sender, instance, created, *args, **kwargs):
    if not getattr(instance, "_river_body_changed", False):
        return
    changed_by = getattr(instance, "_river_changed_by", None) or instance.updated_by
    FunctionRevision.objects.create(
        function=instance,
        version=instance.version,
        action=FunctionRevision.ACTION_CREATED if created else FunctionRevision.ACTION_UPDATED,
        body=instance.body,
        diff=_diff(instance._river_previous_body, instance.body),
        changed_by=changed_by,
        changed_by_username=_username_snapshot(changed_by),
    )


pre_save.connect(on_pre_save, Function)
post_save.connect(on_post_save, Function)


def _normalize_callback(callback):
    callback_str = inspect.getsource(callback).replace("def %s(" % callback.__name__, "def handle(")
    space_size = callback_str.index('def handle(')
    return re.sub(r'^\s{%s}' % space_size, '', inspect.getsource(callback).replace("def %s(" % callback.__name__, "def handle("))


def create_function(callback):
    """
    Registers a plain Python function (defined in your codebase, reviewed
    via git/CI like any other code) as a river.Function row, because
    Hook.callback_function is a mandatory FK to Function. Since the body
    comes from source code rather than a hand-typed admin edit, it is
    auto-approved: there is nothing for a reviewer to sign off on that
    wasn't already reviewed as a normal pull request.
    """
    function, created = Function.objects.get_or_create(
        name=callback.__module__ + "." + callback.__name__,
        body=_normalize_callback(callback)
    )
    if created and not function.is_approved:
        function.is_approved = True
        function.approved_at = timezone.now()
        function.save(update_fields=["is_approved", "approved_at"])
    return function
