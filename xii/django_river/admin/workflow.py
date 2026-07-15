from django import forms
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType

from xii.django_river.core.workflowregistry import workflow_registry
from xii.django_river.models import Workflow


def get_workflow_choices():
    # workflow_registry.workflows is keyed by the model class itself (not
    # id(cls) or a class_index lookup table - that indirection was removed
    # in an earlier pass but this loop was never updated, so it raised
    # AttributeError on every Workflow add/change admin page load.
    result = []
    for cls, field_names in workflow_registry.workflows.items():
        content_type = ContentType.objects.get_for_model(cls)
        for field_name in field_names:
            result.append(("%s %s" % (content_type.pk, field_name), "%s.%s - %s" % (cls.__module__, cls.__name__, field_name)))
    return result


class WorkflowForm(forms.ModelForm):
    workflow = forms.ChoiceField(choices=[])

    class Meta:
        model = Workflow
        fields = ('workflow', 'initial_state')

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance", None)
        self.declared_fields['workflow'].choices = get_workflow_choices()
        if instance and instance.pk:
            self.declared_fields['workflow'].initial = "%s %s" % (instance.content_type.pk, instance.field_name)

        super(WorkflowForm, self).__init__(*args, **kwargs)

    def clean_workflow(self):
        # In practice this ChoiceField already rejects anything outside its
        # generated "<content_type_pk> <field_name>" choices before this
        # method ever runs, so the empty/no-space case below is normally
        # unreachable. It's kept as a real validation error (rather than
        # silently returning (None, None), which used to let `save()` crash
        # confusingly with ContentType.DoesNotExist) as a defense-in-depth
        # guard in case the choices format ever changes.
        value = self.cleaned_data.get('workflow')
        if not value or ' ' not in value:
            raise forms.ValidationError("Select a valid workflow/field combination.")
        return value.split(" ")

    def save(self, *args, **kwargs):
        content_type_pk, field_name = self.cleaned_data.get('workflow')
        instance = super(WorkflowForm, self).save(commit=False)
        instance.content_type = ContentType.objects.get(pk=content_type_pk)
        instance.field_name = field_name
        return super(WorkflowForm, self).save(*args, **kwargs)


# noinspection PyMethodMayBeStatic
class WorkflowAdmin(admin.ModelAdmin):
    form = WorkflowForm
    # 'field_name' is a real field on Workflow - no custom method needed (there
    # used to be one here, shadowing it with `obj.workflow.field_name`, which
    # doesn't exist on a Workflow instance and raised AttributeError on every
    # changelist render; nothing exercised this admin page in tests, so it
    # went unnoticed).
    list_display = ('model_class', 'field_name', 'initial_state')
    list_select_related = ('content_type', 'initial_state')

    def model_class(self, obj):
        cls = obj.content_type.model_class()
        if cls:
            return "%s.%s" % (cls.__module__, cls.__name__)
        else:
            return "Class not found in the workspace"


admin.site.register(Workflow, WorkflowAdmin)
