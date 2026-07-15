from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase
from hamcrest import assert_that, calling, contains_exactly, equal_to, has_length, raises

from xii.django_river.models.function import Function, FunctionRevision

User = get_user_model()


class FunctionApprovalTest(TestCase):

    def setUp(self):
        self.author = User.objects.create(username="author")
        self.reviewer = User.objects.create(username="reviewer")

    def _create_as_author(self, body="def handle(context):\n    context['touched'] = True"):
        function = Function(name="fn", body=body, created_by=self.author, updated_by=self.author)
        function._river_changed_by = self.author
        function.save()
        return function

    def test_shouldNotExecuteUnapprovedFunction(self):
        function = self._create_as_author()
        assert_that(calling(function.get), raises(ImproperlyConfigured))

    def test_shouldExecuteAfterApprovalByAnotherReviewer(self):
        function = self._create_as_author()
        function.approve(self.reviewer)
        callback = function.get()
        context = {}
        callback(context)
        assert_that(context.get("touched"), equal_to(True))
        assert_that(function.is_approved, equal_to(True))
        assert_that(function.approved_by_id, equal_to(self.reviewer.pk))

    def test_shouldBlockSelfApprovalWithoutPermission(self):
        function = self._create_as_author()
        assert_that(
            calling(function.approve).with_args(self.author, allow_self_approval=False),
            raises(ImproperlyConfigured),
        )
        assert_that(function.is_approved, equal_to(False))

    def test_shouldAllowSelfApprovalWithPermissionAndRecordIt(self):
        function = self._create_as_author()
        function.approve(self.author, allow_self_approval=True)
        assert_that(function.is_approved, equal_to(True))

        actions = list(
            FunctionRevision.objects.filter(function=function).order_by("id").values_list("action", flat=True)
        )
        assert_that(actions, contains_exactly(FunctionRevision.ACTION_CREATED, FunctionRevision.ACTION_SELF_APPROVED))

    def test_editingBodyResetsApproval(self):
        function = self._create_as_author()
        function.approve(self.reviewer)
        assert_that(function.is_approved, equal_to(True))

        function.body = "def handle(context):\n    context['touched'] = False"
        function._river_changed_by = self.author
        function.save()

        function.refresh_from_db()
        assert_that(function.is_approved, equal_to(False))
        assert_that(calling(function.get), raises(ImproperlyConfigured))

    def test_editingWithoutChangingBodyDoesNotResetApprovalOrCreateRevision(self):
        function = self._create_as_author()
        function.approve(self.reviewer)

        function.name = "renamed"
        function._river_changed_by = self.author
        function.save()

        function.refresh_from_db()
        assert_that(function.is_approved, equal_to(True))
        # CREATED (on create) + SELF/APPROVED (on approve) only — the rename
        # didn't touch the body, so no extra revision should be logged.
        assert_that(FunctionRevision.objects.filter(function=function), has_length(2))

    def test_cacheKeyIsScopedPerConnectionSchemaToAvoidCrossTenantReuse(self):
        function = self._create_as_author()
        function.approve(self.reviewer)
        key = function._cache_key()
        assert_that(key[1], equal_to(function.pk))

    def test_revisionsSnapshotUsernameSoHistorySurvivesAccountDeletion(self):
        function = self._create_as_author()
        function.approve(self.reviewer)

        created_revision = FunctionRevision.objects.get(function=function, action=FunctionRevision.ACTION_CREATED)
        approved_revision = FunctionRevision.objects.get(function=function, action=FunctionRevision.ACTION_APPROVED)
        assert_that(created_revision.changed_by_username, equal_to("author"))
        assert_that(approved_revision.changed_by_username, equal_to("reviewer"))

        self.reviewer.delete()
        approved_revision.refresh_from_db()
        assert_that(approved_revision.changed_by_id, equal_to(None))
        assert_that(approved_revision.changed_by_username, equal_to("reviewer"))
