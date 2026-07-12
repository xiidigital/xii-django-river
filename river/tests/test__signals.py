from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, equal_to, has_entries

from river import signals
from river.models.factories import PermissionObjectFactory, UserObjectFactory
from river.tests.models import BasicTestModel
from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState


class SignalTest(TestCase):

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)
        self.received = []

    def _receiver(self, signal_name):
        def receiver(sender, **kwargs):
            self.received.append((signal_name, sender, kwargs))

        return receiver

    def test_shouldEmitAllSignalsOnApprovalThatTransitionsAndCompletesTheWorkflow(self):
        authorized_permission = PermissionObjectFactory()
        authorized_user = UserObjectFactory(user_permissions=[authorized_permission])

        state1 = RawState("state1")
        state2 = RawState("state2")

        authorization_policies = [AuthorizationPolicyBuilder().with_permission(authorized_permission).build()]
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, authorization_policies) \
            .build()

        workflow_object = flow.objects[0]

        receivers = []
        for name in ["pre_approve", "post_approve", "pre_transition", "post_transition", "pre_on_complete", "post_on_complete"]:
            receiver = self._receiver(name)
            receivers.append((getattr(signals, name), receiver))
            getattr(signals, name).connect(receiver)

        try:
            workflow_object.river.my_field.approve(as_user=authorized_user)
        finally:
            for signal, receiver in receivers:
                signal.disconnect(receiver)

        fired = [name for name, sender, kwargs in self.received]
        assert_that(fired, equal_to(["pre_approve", "pre_transition", "pre_on_complete", "post_on_complete", "post_transition", "post_approve"]))

        for name, sender, kwargs in self.received:
            assert_that(sender, equal_to(BasicTestModel))
            assert_that(kwargs["workflow_object"], equal_to(workflow_object))
            assert_that(kwargs["field_name"], equal_to("my_field"))

        transition_kwargs = dict((name, kwargs) for name, sender, kwargs in self.received)
        assert_that(transition_kwargs["post_transition"], has_entries(
            source_state=flow.get_state(state1),
            destination_state=flow.get_state(state2),
        ))

    def test_shouldNotEmitTransitionOrCompleteSignalsWhenApprovalDoesNotTransition(self):
        permission1 = PermissionObjectFactory()
        permission2 = PermissionObjectFactory()
        user1 = UserObjectFactory(user_permissions=[permission1])

        state1 = RawState("state1")
        state2 = RawState("state2")

        authorization_policies = [
            AuthorizationPolicyBuilder().with_priority(0).with_permission(permission1).build(),
            AuthorizationPolicyBuilder().with_priority(1).with_permission(permission2).build(),
        ]
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, authorization_policies) \
            .build()

        workflow_object = flow.objects[0]

        receivers = []
        for name in ["pre_transition", "post_transition", "pre_on_complete", "post_on_complete"]:
            receiver = self._receiver(name)
            receivers.append((getattr(signals, name), receiver))
            getattr(signals, name).connect(receiver)

        try:
            workflow_object.river.my_field.approve(as_user=user1)
        finally:
            for signal, receiver in receivers:
                signal.disconnect(receiver)

        assert_that(self.received, equal_to([]))
