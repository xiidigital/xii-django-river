from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import TestCase
from hamcrest import assert_that, calling, equal_to, raises

from river.models import OnCompleteHook, State, Workflow
from river.models.function import Function
from river.models.hook import AFTER
from river.tests.models import BasicTestModel


class HookApprovalGateTest(TestCase):

    def setUp(self):
        content_type = ContentType.objects.get_for_model(BasicTestModel)
        state = State.objects.create(label="state1")
        self.workflow = Workflow.objects.create(field_name="my_field", content_type=content_type, initial_state=state)

    def test_shouldRefuseToSaveHookWithUnapprovedFunction(self):
        function = Function.objects.create(name="fn", body="def handle(context):\n    pass")
        assert_that(function.is_approved, equal_to(False))
        assert_that(
            calling(OnCompleteHook.objects.create).with_args(
                workflow=self.workflow, callback_function=function, hook_type=AFTER
            ),
            raises(ValidationError),
        )
        assert_that(OnCompleteHook.objects.count(), equal_to(0))

    def test_shouldAllowSavingHookWithApprovedFunction(self):
        function = Function.objects.create(name="fn2", body="def handle(context):\n    pass", is_approved=True)
        hook = OnCompleteHook.objects.create(workflow=self.workflow, callback_function=function, hook_type=AFTER)
        assert hook.pk is not None
