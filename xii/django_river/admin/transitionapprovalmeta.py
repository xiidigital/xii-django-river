from django.contrib import admin
from django import forms

from xii.django_river.models.transitionapprovalmeta import TransitionApprovalMeta


class TransitionApprovalMetaForm(forms.ModelForm):
    class Meta:
        model = TransitionApprovalMeta
        fields = ('workflow', 'transition_meta', 'permissions', 'groups', 'priority')


class TransitionApprovalMetaAdmin(admin.ModelAdmin):
    form = TransitionApprovalMetaForm
    list_display = ('workflow', 'transition_meta', 'priority')
    list_select_related = ('workflow', 'transition_meta')


admin.site.register(TransitionApprovalMeta, TransitionApprovalMetaAdmin)
