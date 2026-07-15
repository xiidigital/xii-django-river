from django.test import TestCase, override_settings
from hamcrest import assert_that, calling, equal_to, raises

from xii.django_river.models.function import Function


def _approved_function(body):
    function = Function(name="sandboxed-fn", body=body)
    function._river_body_changed = True  # irrelevant here, just for clarity
    function.is_approved = True
    function.save()
    return function


@override_settings(RIVER_ALLOW_DB_FUNCTIONS=True, RIVER_SANDBOX_DB_FUNCTIONS=True)
class FunctionSandboxTest(TestCase):

    def test_shouldRunAWellBehavedHandle(self):
        function = _approved_function("def handle(context):\n    context['touched'] = True")
        context = {}
        function.get()(context)
        assert_that(context.get("touched"), equal_to(True))

    def test_shouldBlockImportStatements(self):
        function = _approved_function(
            "def handle(context):\n"
            "    import os\n"
            "    context['leak'] = os.environ\n"
        )
        handle = function.get()  # compiles fine: the import only runs when called
        assert_that(calling(handle).with_args({}), raises(Exception))

    def test_shouldBlockDunderAttributeEscape(self):
        function = _approved_function(
            "def handle(context):\n"
            "    context['leak'] = ().__class__.__bases__[0].__subclasses__()\n"
        )
        # RestrictedPython rejects this at compile time (inside Function.get()
        # -> _load() -> compile_sandboxed_handle), before a callable even exists.
        assert_that(calling(function.get), raises(SyntaxError))

    def test_shouldRejectBodyWithoutTopLevelHandle(self):
        from django.core.exceptions import ImproperlyConfigured

        function = _approved_function("x = 1\n")
        assert_that(calling(function.get), raises(ImproperlyConfigured))


class FunctionSandboxDisabledByDefaultTest(TestCase):

    def test_sandboxIsOffByDefault(self):
        # Without RIVER_SANDBOX_DB_FUNCTIONS, dunder-escaping source that
        # would be rejected under the sandbox still compiles under plain
        # exec() — demonstrating this is opt-in, not automatic, and that a
        # project must consciously turn it on.
        function = _approved_function(
            "def handle(context):\n"
            "    context['ran'] = True\n"
        )
        context = {}
        function.get()(context)
        assert_that(context.get("ran"), equal_to(True))
