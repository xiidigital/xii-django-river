from django.contrib.contenttypes.models import ContentType
from hamcrest import assert_that, none

from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.tests.hooking.base_hooking_test import BaseHookingTest
from xii.django_river.tests.models import ModelForSlowCase1, ModelForSlowCase2
# noinspection DuplicatedCode
from rivertest.flowbuilder import RawState, AuthorizationPolicyBuilder, FlowBuilder


class CrossContentTypeHookIsolationTest(BaseHookingTest):
    """
    Regression test: the OnCompleteHook lookup in signals.py's OnCompleteSignal
    used to filter by `workflow__field_name=self.field_name` - a bare string
    match against *any* Workflow row with that field name - instead of
    `workflow=self.workflow`, the exact FK for this content type/workflow.
    OnCompleteHook has no transition/transition_meta FK to narrow it back down
    (unlike OnTransitHook/OnApprovedHook), so a workflow-level hook
    (object_id=None) registered for one content type would fire for any other
    content type whose StateField happens to share the same field name (very
    plausible - "status" is a common choice). ModelForSlowCase1/ModelForSlowCase2
    both use "status" here, which is exactly this collision.
    """

    def test_globalOnCompleteHookOnOneContentTypeDoesNotFireForAnotherContentTypeWithTheSameFieldName(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])

        content_type_1 = ContentType.objects.get_for_model(ModelForSlowCase1)
        content_type_2 = ContentType.objects.get_for_model(ModelForSlowCase2)

        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]

        flow1 = FlowBuilder("status", content_type_1) \
            .with_object_factory(lambda: ModelForSlowCase1.objects.create()) \
            .with_transition(state1, state2, policies) \
            .build()

        flow2 = FlowBuilder("status", content_type_2) \
            .with_object_factory(lambda: ModelForSlowCase2.objects.create()) \
            .with_transition(state1, state2, policies) \
            .build()

        # Workflow-level on-complete hook (no workflow_object) registered
        # only against flow1's (ModelForSlowCase1) workflow.
        self.hook_pre_complete(flow1.workflow)

        assert_that(self.get_output(), none())

        # Completing the ModelForSlowCase2 object's workflow (different
        # content type, same field name "status") must not trigger flow1's
        # on-complete hook.
        flow2.objects[0].river.status.approve(as_user=user)

        assert_that(self.get_output(), none())
