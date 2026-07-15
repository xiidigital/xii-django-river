from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from hamcrest import assert_that, calling, raises, equal_to

from xii.django_river.models.function import create_function


def _callback(context):
    context["touched"] = True


class FunctionGateTest(TestCase):

    def test_shouldExecuteDbFunctionsWhenEnabled(self):
        function = create_function(_callback)
        context = {}
        function.get()(context)
        assert_that(context.get("touched"), equal_to(True))

    @override_settings(RIVER_ALLOW_DB_FUNCTIONS=False)
    def test_shouldRefuseToLoadDbFunctionsWhenDisabled(self):
        function = create_function(_callback)
        assert_that(calling(function.get), raises(ImproperlyConfigured))
