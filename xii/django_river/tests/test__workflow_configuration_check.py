from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, has_item, contains_string, is_not

from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState
from xii.django_river.apps import check_workflow_configuration
from xii.django_river.models import State
from xii.django_river.models.factories import PermissionObjectFactory
from xii.django_river.tests.models import BasicTestModel


class WorkflowConfigurationCheckTest(TestCase):

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    def _codes(self, warnings):
        return [w.id for w in warnings]

    def test_shouldWarnAboutATransitionWithNoAuthorizationRuleAtAll(self):
        state1, state2 = RawState("state1"), RawState("state2")
        FlowBuilder("my_field", self.content_type).with_transition(state1, state2).build()

        warnings = check_workflow_configuration(None)

        assert_that(self._codes(warnings), has_item("xii_django_river.W002"))

    def test_shouldWarnAboutAnExplicitRuleWithNoPermissionsOrGroups(self):
        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().build()]  # no permission, no group
        FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()

        warnings = check_workflow_configuration(None)

        assert_that(self._codes(warnings), has_item("xii_django_river.W003"))

    def test_shouldNotWarnWhenATransitionHasAProperlyRestrictedRule(self):
        permission = PermissionObjectFactory()
        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()

        warnings = check_workflow_configuration(None)

        assert_that(self._codes(warnings), is_not(has_item("xii_django_river.W002")))
        assert_that(self._codes(warnings), is_not(has_item("xii_django_river.W003")))

    def test_shouldWarnAboutAnOrphanedState(self):
        State.objects.create(label="nowhere-used-state")

        warnings = check_workflow_configuration(None)

        assert_that(self._codes(warnings), has_item("xii_django_river.W004"))
        messages = [str(w.msg) for w in warnings if w.id == "xii_django_river.W004"]
        assert_that(messages, has_item(contains_string("nowhere-used-state")))
