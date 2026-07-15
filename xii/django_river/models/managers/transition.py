from xii.django_river.models.managers.rivermanager import RiverManager
from xii.django_river.models.managers.transitionapproval import WorkflowObjectFilteringMixin


class TransitionManager(WorkflowObjectFilteringMixin, RiverManager):
    pass
