from django.contrib import admin

from xii.django_river.models.transition_audit_log import TransitionAuditLog


@admin.register(TransitionAuditLog)
class TransitionAuditLogAdmin(admin.ModelAdmin):
    """
    Read-only by design: this is an audit trail, not a working table. Nobody
    - including superusers - edits or deletes rows here; they're written
    exclusively from InstanceWorkflowObject (approve / cancel_impossible_future
    / jump_to).
    """

    list_display = (
        'date_created', 'workflow', 'action', 'source_state', 'destination_state',
        'actor_username', 'content_type', 'object_id',
    )
    list_select_related = ('workflow', 'source_state', 'destination_state', 'content_type')
    list_filter = ('action', 'workflow', 'content_type')
    search_fields = ('actor_username', 'object_id')
    readonly_fields = [f.name for f in TransitionAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
