from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from hamcrest import assert_that, equal_to

from rivertest.flowbuilder import FlowBuilder, RawState
from xii.django_river.models import Workflow
from xii.django_river.models.factories import UserObjectFactory
from xii.django_river.tests.models import BasicTestModel


class WorkflowAdminTest(TestCase):
    """
    Regression test for a real bug: ``WorkflowAdmin`` used to define its own
    ``field_name(self, obj)`` method that did ``return obj.workflow.field_name``,
    shadowing the real ``Workflow.field_name`` model field. Since a ``Workflow``
    instance has no ``.workflow`` attribute, every render of this changelist
    raised ``AttributeError`` - nothing exercised this page, so it went
    unnoticed. This test renders the actual changelist through the admin site
    so this class of bug can't recur silently.
    """

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)
        self.superuser = UserObjectFactory(is_staff=True, is_superuser=True)
        self.superuser.set_password("password")
        self.superuser.save()

    def test_changelistRendersWithoutError(self):
        state1, state2 = RawState("state1"), RawState("state2")
        FlowBuilder("my_field", self.content_type).with_transition(state1, state2).build()

        assert_that(Workflow.objects.exists(), equal_to(True))

        self.client.login(username=self.superuser.get_username(), password="password")
        url = reverse("admin:xii_django_river_workflow_changelist")
        response = self.client.get(url)

        assert_that(response.status_code, equal_to(200))

    def test_addPageRendersWithoutError(self):
        # Regression test for a second, sibling bug: WorkflowForm's
        # get_workflow_choices() called workflow_registry.class_index, an
        # attribute that no longer exists since WorkflowRegistry was keyed
        # by model class directly - this crashed the Workflow add/change page
        # with AttributeError every time it was opened.
        state1, state2 = RawState("state1"), RawState("state2")
        FlowBuilder("my_field", self.content_type).with_transition(state1, state2).build()

        self.client.login(username=self.superuser.get_username(), password="password")
        url = reverse("admin:xii_django_river_workflow_add")
        response = self.client.get(url)

        assert_that(response.status_code, equal_to(200))
