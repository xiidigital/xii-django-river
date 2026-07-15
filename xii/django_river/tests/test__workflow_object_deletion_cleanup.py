from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, has_length, equal_to

from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState
from xii.django_river.models import Transition, TransitionApproval
from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.models.transition_audit_log import TransitionAuditLog
from xii.django_river.tests.models import BasicTestModel


class WorkflowObjectDeletionCleanupTest(TestCase):
    """
    Regression test, real bug found while investigating dangling
    Transition/TransitionApproval rows: deleting a workflow object with any
    approved transition didn't just leave orphans - it crashed outright with
    ProtectedError. The `<field>_transitions`/`<field>_transition_approvals`
    GenericRelations (models/fields/state.py) make Django's deletion
    collector try to CASCADE-delete Transition/TransitionApproval when the
    object goes away, but TransitionApproval.transition was on_delete=PROTECT
    - so the collector found a Transition it was about to cascade-delete
    still "protected" by a TransitionApproval that was itself also being
    cascade-deleted in the very same operation, and refused the whole delete.
    Fixed by changing that FK to CASCADE (migration 0003); nothing in this
    codebase ever deleted a Transition outside of this exact cascade path, so
    PROTECT wasn't guarding anything real. TransitionAuditLog is untouched by
    design either way - it's an append-only audit trail meant to survive the
    object it describes being deleted.
    """

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    def test_deletingTheWorkflowObjectDeletesItsTransitionsAndApprovalsButKeepsTheAuditLog(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])

        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()
        workflow_object = flow.objects[0]

        workflow_object.river.my_field.approve(as_user=user)

        object_id = workflow_object.pk
        assert_that(Transition.objects.filter(object_id=object_id, content_type=self.content_type), has_length(1))
        assert_that(TransitionApproval.objects.filter(object_id=object_id, content_type=self.content_type), has_length(1))
        audit_entries_before = TransitionAuditLog.objects.filter(object_id=object_id, content_type=self.content_type).count()
        assert_that(audit_entries_before, equal_to(1))

        workflow_object.delete()

        assert_that(Transition.objects.filter(object_id=object_id, content_type=self.content_type), has_length(0))
        assert_that(TransitionApproval.objects.filter(object_id=object_id, content_type=self.content_type), has_length(0))
        # The audit trail survives - same principle as FunctionRevision
        # surviving its Function being deleted.
        assert_that(
            TransitionAuditLog.objects.filter(object_id=object_id, content_type=self.content_type).count(),
            equal_to(audit_entries_before),
        )
