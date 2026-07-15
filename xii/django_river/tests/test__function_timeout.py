from django.test import TestCase, override_settings
from hamcrest import assert_that, calling, raises, is_

from xii.django_river.models.function import Function
from xii.django_river.timeout import FunctionTimeoutError


def _approved_function(name, body):
    function = Function(name=name, body=body)
    function._river_body_changed = True
    function.is_approved = True
    function.save()
    return function


@override_settings(RIVER_ALLOW_DB_FUNCTIONS=True)
class FunctionTimeoutTest(TestCase):

    def test_shouldNotTimeOutAWellBehavedFunctionWithinTheLimit(self):
        function = _approved_function("well-behaved", "def handle(context):\n    context['ran'] = True")
        with override_settings(RIVER_FUNCTION_TIMEOUT_SECONDS=1):
            context = {}
            function.get()(context)
        assert_that(context, is_({"ran": True}))

    def test_shouldRaiseFunctionTimeoutErrorWhenTheFunctionRunsTooLong(self):
        function = _approved_function("runaway", "def handle(context):\n    while True:\n        pass")
        with override_settings(RIVER_FUNCTION_TIMEOUT_SECONDS=1):
            assert_that(calling(function.get()).with_args({}), raises(FunctionTimeoutError))

    def test_shouldNotEnforceAnyTimeoutWhenSettingIsUnset(self):
        # Default (RIVER_FUNCTION_TIMEOUT_SECONDS unset) - unbounded, exactly
        # as before this feature existed. A short-running function is used
        # here (not a real infinite loop) so the test itself doesn't hang.
        function = _approved_function("no-timeout-configured", "def handle(context):\n    context['ran'] = True")
        context = {}
        function.get()(context)
        assert_that(context, is_({"ran": True}))
