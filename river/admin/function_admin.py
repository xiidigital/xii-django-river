from django import forms
from django.contrib import admin

from river.models import Function

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


class FunctionAdmin(admin.ModelAdmin):
    form = FunctionForm
    list_display = ('name', 'function_version', 'date_created', 'date_updated')
    readonly_fields = ('version', 'date_created', 'date_updated')

    def function_version(self, obj):  # pylint: disable=no-self-use
        return "v%s" % obj.version


admin.site.register(Function, FunctionAdmin)
