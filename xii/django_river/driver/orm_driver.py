from django.contrib import auth
from django.db.models import Min, CharField, Q, F
from django.db.models.functions import Cast
from django_cte import CTE, with_cte

from xii.django_river.driver.river_driver import RiverDriver
from xii.django_river.models import TransitionApproval, PENDING


class OrmDriver(RiverDriver):

    def get_available_approvals(self, as_user):
        those_with_max_priority = CTE(
            TransitionApproval.objects.filter(
                workflow=self.workflow, status=PENDING
            ).values(
                'workflow', 'object_id', 'transition'
            ).annotate(min_priority=Min('priority'))
        )

        workflow_objects = CTE(
            self.workflow_object_class.objects.all(),
            name="workflow_object"
        )

        # Uses the module-level `with_cte(cte, select=...)` helper instead of
        # the deprecated `CTEQuerySet.with_cte()` instance method (django_cte
        # marks the latter, and CTEManager/CTEQuerySet themselves, deprecated
        # in favor of this). It works on any queryset - not just one built
        # from a CTEManager - which is what lets TransitionApprovalManager
        # (models/managers/transitionapproval.py) drop its former
        # IS_MSSQL-at-class-definition-time base class switch entirely.
        approvals_with_max_priority = with_cte(
            those_with_max_priority,
            select=those_with_max_priority.join(
                self._authorized_approvals(as_user),
                workflow_id=those_with_max_priority.col.workflow,
                object_id=those_with_max_priority.col.object_id,
                transition_id=those_with_max_priority.col.transition,
            )
        ).annotate(
            object_id_as_str=Cast('object_id', CharField(max_length=200)),
            min_priority=those_with_max_priority.col.min_priority
        ).filter(min_priority=F("priority"))

        return with_cte(
            workflow_objects,
            select=workflow_objects.join(
                approvals_with_max_priority, object_id_as_str=Cast(workflow_objects.col.pk, CharField(max_length=200))
            )
        ).filter(transition__source_state=getattr(workflow_objects.col, self.field_name + "_id"))

    def _authorized_approvals(self, as_user):
        group_q = Q(groups__in=as_user.groups.all())

        permissions = []
        for backend in auth.get_backends():
            permissions.extend(backend.get_all_permissions(as_user))

        permission_q = Q()
        for p in permissions:
            label, codename = p.split('.')
            permission_q = permission_q | Q(permissions__content_type__app_label=label,
                                            permissions__codename=codename)

        return TransitionApproval.objects.filter(
            Q(workflow=self.workflow, status=PENDING) &
            (
                    (Q(transactioner__isnull=True) | Q(transactioner=as_user)) &
                    (Q(permissions__isnull=True) | permission_q) &
                    (Q(groups__isnull=True) | group_q)
            )
        )
