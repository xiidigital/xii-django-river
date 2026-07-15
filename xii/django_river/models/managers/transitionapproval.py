from xii.django_river.config import app_config
from xii.django_river.models.managers.rivermanager import RiverManager


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


class TransitionApprovalManager(WorkflowObjectFilteringMixin, RiverManager):
    # Used to conditionally subclass CTEManager instead of RiverManager when
    # not on MSSQL, decided once at class-definition/import time (a real bug:
    # app_config.IS_MSSQL is meant to be read fresh on every access, like the
    # rest of RiverConfig, not baked into a class hierarchy at import time).
    # No longer needed: OrmDriver (driver/orm_driver.py) now attaches CTEs via
    # django_cte's module-level `with_cte()` helper, which works on any
    # queryset - it doesn't require the manager's queryset class to inherit
    # from CTEQuerySet. RiverManager (its RiverQuerySet already branches on
    # app_config.IS_MSSQL per-call for `.first()`) is a single base that's
    # correct on every backend.
    pass
