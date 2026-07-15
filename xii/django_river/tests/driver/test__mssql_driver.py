from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from hamcrest import assert_that, equal_to, is_not, contains_string

from xii.django_river.driver.mssql_driver import MsSqlDriver
from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.tests.models import BasicTestModel
from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState


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
