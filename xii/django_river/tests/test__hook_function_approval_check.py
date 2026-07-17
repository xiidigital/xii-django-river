from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, has_item, is_not

from xii.django_river.apps import check_hooks_with_unapproved_functions
from xii.django_river.models import OnCompleteHook, State, Workflow
from xii.django_river.models.function import Function
from xii.django_river.models.hook import AFTER
from xii.django_river.tests.models import BasicTestModel


class HookFunctionApprovalCheckTest(TestCase):
    """
    Hook.save() only validates its callback_function is approved at the
    moment the Hook is saved (see test__hook_approval_gate.py). Editing that
    Function's body afterwards resets is_approved without touching any Hook
    already pointing to it - this check (xii_django_river.W005) is what
    surfaces that after the fact.
    """

    def setUp(self):
        content_type = ContentType.objects.get_for_model(BasicTestModel)
        state = State.objects.create(label="state1")
        self.workflow = Workflow.objects.create(field_name="my_field", content_type=content_type, initial_state=state)

    def _codes(self, warnings):
        return [w.id for w in warnings]

    def test_shouldWarnWhenAnApprovedHooksFunctionLosesApprovalAfterTheFact(self):
        function = Function.objects.create(name="fn", body="def handle(context):\n    pass", is_approved=True)
        OnCompleteHook.objects.create(workflow=self.workflow, callback_function=function, hook_type=AFTER)

        # Editing the body resets is_approved (Function.on_pre_save) without
        # touching the Hook that already points to this Function.
        function.body = "def handle(context):\n    pass  # changed"
        function.save()
        assert_that(function.is_approved, is_not(True))

        warnings = check_hooks_with_unapproved_functions(None)

        assert_that(self._codes(warnings), has_item("xii_django_river.W005"))

    def test_shouldNotWarnWhenTheHooksFunctionIsStillApproved(self):
        function = Function.objects.create(name="fn2", body="def handle(context):\n    pass", is_approved=True)
        OnCompleteHook.objects.create(workflow=self.workflow, callback_function=function, hook_type=AFTER)

        warnings = check_hooks_with_unapproved_functions(None)

        assert_that(self._codes(warnings), is_not(has_item("xii_django_river.W005")))
