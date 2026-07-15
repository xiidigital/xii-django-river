from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from hamcrest import assert_that, equal_to, is_not, contains_string, has_item

from xii.django_river.driver.mssql_driver import MsSqlDriver
from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.tests.models import BasicTestModel
from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState


class _ObjectLevelPermissionBackend:
    """
    Minimal stand-in for a custom auth backend (e.g. django-guardian) that
    grants a permission the user doesn't hold via user_permissions/groups.
    """

    def authenticate(self, request, **kwargs):
        return None

    def get_all_permissions(self, user_obj, obj=None):
        return {"xii_django_river.custom_backend_permission"}


class MsSqlDriverQueryBuildingTest(TestCase):
    """
    No SQL Server disponible en CI: valida la construcción de la consulta
    (identificadores resueltos y parámetros alineados con los placeholders).
    """

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    def test_shouldBuildParametrizedQueryWithMatchingPlaceholders(self):
        authorized_permission = PermissionObjectFactory()
        authorized_user = UserObjectFactory(user_permissions=[authorized_permission])

        state1 = RawState("state1")
        state2 = RawState("state2")

        authorization_policies = [AuthorizationPolicyBuilder().with_permission(authorized_permission).build()]
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, authorization_policies) \
            .build()

        driver = MsSqlDriver(flow.workflow, BasicTestModel, "my_field")
        sql, params = driver._build_query(authorized_user)

        assert_that(sql.count("%s"), equal_to(len(params)))
        assert_that(sql, is_not(contains_string("{")))
        assert_that(sql, is_not(contains_string("}")))
        assert_that(sql, contains_string("xii_django_river_transitionapproval"))
        assert_that(params[1], equal_to("pending"))
        assert_that(params[4], equal_to(authorized_user.pk))

    def test_shouldUseSentinelIdsWhenUserHasNoPermissionsNorGroups(self):
        user = UserObjectFactory()

        state1 = RawState("state1")
        state2 = RawState("state2")
        flow = FlowBuilder("my_field", self.content_type) \
            .with_transition(state1, state2, [AuthorizationPolicyBuilder().build()]) \
            .build()

        driver = MsSqlDriver(flow.workflow, BasicTestModel, "my_field")
        sql, params = driver._build_query(user)

        assert_that(sql.count("%s"), equal_to(len(params)))
        assert_that(params[-2:], equal_to([-1, -1]))

    @override_settings(AUTHENTICATION_BACKENDS=[
        "django.contrib.auth.backends.ModelBackend",
        "xii.django_river.tests.driver.test__mssql_driver._ObjectLevelPermissionBackend",
    ])
    def test_permissionIdsIncludePermissionsGrantedOnlyByACustomAuthBackend(self):
        # Regression test: _permission_ids used to only look at
        # user_permissions/group-assigned Permission rows directly, missing
        # anything granted purely through a custom auth backend (unlike
        # OrmDriver, which already goes through auth.get_backends()). A user
        # authorized only via such a backend would be silently denied
        # approvals on MSSQL that they'd be granted on any other database.
        permission = PermissionObjectFactory(
            codename="custom_backend_permission",
            content_type__app_label="xii_django_river",
        )
        user = UserObjectFactory()  # no direct permissions, no groups

        permission_ids = MsSqlDriver._permission_ids(user)

        assert_that(permission_ids, has_item(permission.pk))
