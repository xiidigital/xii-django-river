from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, equal_to, has_length

from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState
from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.models.transition_audit_log import TransitionAuditLog
from xii.django_river.tests.models import BasicTestModel


class TransitionAuditLogTest(TestCase):

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    def test_shouldRecordAnApprovedEntryWithTheApprovingUser(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])

        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()
        workflow_object = flow.objects[0]

        workflow_object.river.my_field.approve(as_user=user)

        logs = TransitionAuditLog.objects.filter(object_id=workflow_object.pk, content_type=self.content_type)
        assert_that(logs, has_length(1))
        log = logs.first()
        assert_that(log.action, equal_to(TransitionAuditLog.ACTION_APPROVED))
        assert_that(log.actor, equal_to(user))
        assert_that(log.actor_username, equal_to(user.get_username()))
        assert_that(log.source_state, equal_to(flow.get_state(state1)))
        assert_that(log.destination_state, equal_to(flow.get_state(state2)))

    def test_shouldRecordCancelledEntriesAttributedToTheApprovingUser(self):
        # Two parallel branches from state1: approving the direct path to
        # state3 should cancel the alternate state1->state2->state3 path,
        # and that cancellation should be attributed to whoever approved
        # the transition that made it impossible.
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])

        state1, state2, state3 = RawState("state1"), RawState("state2"), RawState("state3")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, policies) \
            .with_transition(state1, state3, policies) \
            .with_transition(state2, state3, policies) \
            .build()
        workflow_object = flow.objects[0]

        workflow_object.river.my_field.approve(as_user=user, next_state=flow.get_state(state3))

        cancelled = TransitionAuditLog.objects.filter(
            object_id=workflow_object.pk, content_type=self.content_type,
            action=TransitionAuditLog.ACTION_CANCELLED,
        )
        # Both legs of the now-impossible alternate route (state1->state2
        # and state2->state3) get cancelled, each attributed to the user
        # whose approval of the direct state1->state3 transition caused it.
        assert_that(cancelled, has_length(2))
        for entry in cancelled:
            assert_that(entry.actor, equal_to(user))
        destination_states = {entry.destination_state for entry in cancelled}
        assert_that(destination_states, equal_to({flow.get_state(state2), flow.get_state(state3)}))

    def test_shouldRecordJumpedEntriesWithTheOptionalActor(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])

        state1, state2, state3 = RawState("state1"), RawState("state2"), RawState("state3")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, policies) \
            .with_transition(state2, state3, policies) \
            .build()
        workflow_object = flow.objects[0]

        workflow_object.river.my_field.jump_to(flow.get_state(state3), as_user=user)

        logs = TransitionAuditLog.objects.filter(
            object_id=workflow_object.pk, content_type=self.content_type,
            action=TransitionAuditLog.ACTION_JUMPED,
        )
        # Jumping straight to state3 skips both intervening transitions
        # (state1->state2 and state2->state3), each logged as JUMPED.
        assert_that(logs, has_length(2))
        for entry in logs:
            assert_that(entry.actor, equal_to(user))
        destination_states = {entry.destination_state for entry in logs}
        assert_that(destination_states, equal_to({flow.get_state(state2), flow.get_state(state3)}))

    def test_jumpToWithoutAUserStillRecordsTheEventWithoutAnActor(self):
        # as_user stays optional - existing callers of jump_to(state) that
        # don't pass one keep working exactly as before.
        state1, state2 = RawState("state1"), RawState("state2")
        flow = FlowBuilder("my_field", self.content_type).with_transition(state1, state2).build()
        workflow_object = flow.objects[0]

        workflow_object.river.my_field.jump_to(flow.get_state(state2))

        logs = TransitionAuditLog.objects.filter(
            object_id=workflow_object.pk, content_type=self.content_type,
            action=TransitionAuditLog.ACTION_JUMPED,
        )
        assert_that(logs, has_length(1))
        assert_that(logs.first().actor, equal_to(None))
        assert_that(logs.first().actor_username, equal_to(""))
