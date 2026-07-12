from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ImproperlyConfigured

from river.models import Function
from river.models.function import FunctionRevision

try:
    from codemirror2.widgets import CodeMirrorEditor

    BODY_WIDGET = CodeMirrorEditor(options={'mode': 'python'})
except ImportError:
    BODY_WIDGET = forms.Textarea(attrs={'rows': 20, 'style': 'font-family: monospace; width: 90%;'})


class FunctionForm(forms.ModelForm):
    body = forms.CharField(widget=BODY_WIDGET)

    class Meta:
        model = Function
        fields = ('name', 'body',)


class FunctionRevisionInline(admin.TabularInline):
    """
    Read-only audit trail: nobody, including superusers, can edit or delete
    past revisions from here. Approving/rejecting new code happens through
    the "Approve selected functions" action, never by touching history.
    """

    model = FunctionRevision
    fields = ('version', 'action', 'changed_by', 'changed_by_username', 'date_created', 'diff')
    readonly_fields = fields
    extra = 0
    can_delete = False
    ordering = ('-version',)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FunctionAdmin(admin.ModelAdmin):
    form = FunctionForm
    list_display = ('name', 'function_version', 'is_approved', 'updated_by', 'approved_by', 'date_updated')
    list_filter = ('is_approved',)
    readonly_fields = ('version', 'date_created', 'date_updated', 'created_by', 'updated_by', 'is_approved', 'approved_by', 'approved_at')
    inlines = [FunctionRevisionInline]
    actions = ['approve_functions']

    def function_version(self, obj):  # pylint: disable=no-self-use
        return "v%s" % obj.version

    def save_model(self, request, obj, form, change):
        # Tag who authored this revision so the audit trail and the
        # self-approval check have someone to compare against.
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        obj._river_changed_by = request.user
        super().save_model(request, obj, form, change)

    def has_approve_permission(self, request):
        return request.user.has_perm('river.approve_function')

    def has_self_approve_permission(self, request):
        return request.user.has_perm('river.self_approve_function')

    @admin.action(description="Approve selected functions for execution")
    def approve_functions(self, request, queryset):
        if not self.has_approve_permission(request):
            self.message_user(
                request,
                "You don't have the river.approve_function permission.",
                level=messages.ERROR,
            )
            return

        allow_self_approval = self.has_self_approve_permission(request)
        approved, self_approved, skipped = 0, 0, 0
        for function in queryset:
            if function.is_approved:
                continue
            is_self = bool(function.updated_by_id and function.updated_by_id == request.user.pk)
            try:
                function.approve(request.user, allow_self_approval=allow_self_approval)
                approved += 1
                if is_self:
                    self_approved += 1
            except ImproperlyConfigured as e:
                skipped += 1
                self.message_user(request, "%s: %s" % (function.name, e), level=messages.WARNING)

        if approved:
            self.message_user(request, "Approved %d function(s)." % approved, level=messages.SUCCESS)
        if self_approved:
            self.message_user(
                request,
                "%d of those were self-approved (author == approver) and are recorded as "
                "SELF_APPROVED in the function's revision history." % self_approved,
                level=messages.WARNING,
            )
        if skipped:
            self.message_user(
                request,
                "%d function(s) were skipped: you authored them and don't have the "
                "river.self_approve_function permission — ask a different reviewer to "
                "approve them." % skipped,
                level=messages.WARNING,
            )


admin.site.register(Function, FunctionAdmin)
