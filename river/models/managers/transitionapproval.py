from django_cte import CTEManager

from river.config import app_config
from river.models.managers.rivermanager import RiverManager


class WorkflowObjectFilteringMixin:
    """
    Traduce el kwarg ``workflow_object`` a la pareja
    ``content_type``/``object_id`` de la GenericForeignKey.
    """

    def filter(self, *args, **kwargs):
        workflow_object = kwargs.pop('workflow_object', None)
        if workflow_object:
            kwargs['content_type'] = app_config.CONTENT_TYPE_CLASS.objects.get_for_model(workflow_object)
            kwargs['object_id'] = workflow_object.pk

        return super().filter(*args, **kwargs)

    def update_or_create(self, *args, **kwargs):
        workflow_object = kwargs.pop('workflow_object', None)
        if workflow_object:
            kwargs['content_type'] = app_config.CONTENT_TYPE_CLASS.objects.get_for_model(workflow_object)
            kwargs['object_id'] = workflow_object.pk

        return super().update_or_create(*args, **kwargs)


class TransitionApprovalManager(WorkflowObjectFilteringMixin, RiverManager if app_config.IS_MSSQL else CTEManager):
    pass
