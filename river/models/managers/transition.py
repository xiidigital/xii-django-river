from river.models.managers.rivermanager import RiverManager
from river.models.managers.transitionapproval import WorkflowObjectFilteringMixin


class TransitionManager(WorkflowObjectFilteringMixin, RiverManager):
    pass
