from django.test import TestCase, override_settings
from hamcrest import assert_that, has_item, is_not

from xii.django_river.apps import check_timeout_with_offthread_executor


class TimeoutExecutorCheckTest(TestCase):
    """
    RIVER_FUNCTION_TIMEOUT_SECONDS relies on signal.alarm (main thread only).
    RIVER_HOOK_EXECUTOR moves hook execution off that thread. Combining both
    silently defeats the timeout - xii_django_river.W006 is meant to catch
    that combination in `manage.py check`.
    """

    def _codes(self, warnings):
        return [w.id for w in warnings]

    @override_settings(RIVER_FUNCTION_TIMEOUT_SECONDS=5, RIVER_HOOK_EXECUTOR='xii.django_river.executors.thread_pool_executor')
    def test_shouldWarnWhenBothSettingsAreSetTogether(self):
        warnings = check_timeout_with_offthread_executor(None)
        assert_that(self._codes(warnings), has_item("xii_django_river.W006"))

    @override_settings(RIVER_FUNCTION_TIMEOUT_SECONDS=5, RIVER_HOOK_EXECUTOR=None)
    def test_shouldNotWarnWhenOnlyTimeoutIsSet(self):
        warnings = check_timeout_with_offthread_executor(None)
        assert_that(self._codes(warnings), is_not(has_item("xii_django_river.W006")))

    @override_settings(RIVER_FUNCTION_TIMEOUT_SECONDS=None, RIVER_HOOK_EXECUTOR='xii.django_river.executors.thread_pool_executor')
    def test_shouldNotWarnWhenOnlyExecutorIsSet(self):
        warnings = check_timeout_with_offthread_executor(None)
        assert_that(self._codes(warnings), is_not(has_item("xii_django_river.W006")))
