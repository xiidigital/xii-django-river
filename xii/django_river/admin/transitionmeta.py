from django import forms
from django.contrib import admin

from xii.django_river.models import TransitionMeta


class TransitionMetaForm(forms.ModelForm):
    class Meta:
        model = TransitionMeta
        fields = ('workflow', 'source_state', 'destination_state')


class TransitionMetaAdmin(admin.ModelAdmin):
    form = TransitionMetaForm
    list_display = ('workflow', 'source_state', 'destination_state')
    list_select_related = ('workflow', 'source_state', 'destination_state')


admin.site.register(TransitionMeta, TransitionMetaAdmin)
