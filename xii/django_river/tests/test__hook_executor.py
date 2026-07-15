import threading
from unittest import mock

from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, override_settings
from hamcrest import assert_that, equal_to, is_

from xii.django_river.models.factories import PermissionObjectFactory, UserObjectFactory
from xii.django_river.models.function import Function
from xii.django_river.models.hook import BEFORE
from xii.django_river.models.on_approved_hook import OnApprovedHook
from xii.django_river.tests.models import BasicTestModel
from rivertest.flowbuilder import AuthorizationPolicyBuilder, FlowBuilder, RawState

# These tests are about the RIVER_HOOK_EXECUTOR dispatch plumbing itself
# (xii/django_river/models/hook.py Hook.execute / xii/django_river/executors.py),
# not about Function's exec()/RestrictedPython execution (covered by
# test__function_gate.py / test__function_sandbox.py). So Hook.execute_now
# is mocked rather than relying on a real stored Function body: a Function
# body runs in its own isolated namespace (see Function._load) and can't
# reach back into this test module's globals to record that it ran.


class HookExecutorTest(TestCase):

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    def _build_approved_flow(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])
        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()
        return flow, user

    def _make_hook(self, flow):
        function = Function.objects.create(name="noop-%s" % id(self), body="def handle(context):\n    pass", is_approved=True)
        return OnApprovedHook.objects.create(
            workflow=flow.workflow, callback_function=function, hook_type=BEFORE,
            transition_approval_meta=flow.transitions_approval_metas[0],
        )

    def test_defaultBehaviorRunsSynchronouslyInline(self):
        # RIVER_HOOK_EXECUTOR unset - unchanged from before this feature
        # existed: execute() calls execute_now() directly, inline.
        flow, user = self._build_approved_flow()
        self._make_hook(flow)

        with mock.patch.object(OnApprovedHook, "execute_now") as execute_now:
            flow.objects[0].river.my_field.approve(as_user=user)

        assert_that(execute_now.call_count, equal_to(1))

    @override_settings(RIVER_HOOK_EXECUTOR="xii.django_river.tests.test__hook_executor._custom_executor")
    def test_configuredExecutorIsConsultedInsteadOfRunningInline(self):
        flow, user = self._build_approved_flow()
        hook = self._make_hook(flow)

        _custom_executor.seen.clear()
        with mock.patch.object(OnApprovedHook, "execute_now") as execute_now:
            flow.objects[0].river.my_field.approve(as_user=user)

        # The configured executor ran instead of the default inline call...
        assert_that(len(_custom_executor.seen), equal_to(1))
        seen_hook, seen_context = _custom_executor.seen[0]
        assert_that(seen_hook.pk, equal_to(hook.pk))
        assert_that(seen_context["hook"]["type"], equal_to("on-approved"))
        # ...and it is *_custom_executor_*'s job to call execute_now, which
        # it does, so the mock still observes exactly one call.
        assert_that(execute_now.call_count, equal_to(1))


def _custom_executor(hook, context):
    """Dotted-path executor referenced by RIVER_HOOK_EXECUTOR above. Records
    what it was called with, then honors the contract by calling execute_now."""
    _custom_executor.seen.append((hook, context))
    hook.execute_now(context)


_custom_executor.seen = []


class ThreadPoolExecutorTest(TestCase):

    def setUp(self):
        super().setUp()
        self.content_type = ContentType.objects.get_for_model(BasicTestModel)

    @override_settings(RIVER_HOOK_EXECUTOR="xii.django_river.executors.thread_pool_executor")
    def test_dispatchesExecuteNowOntoABackgroundThread(self):
        permission = PermissionObjectFactory()
        user = UserObjectFactory(user_permissions=[permission])
        state1, state2 = RawState("state1"), RawState("state2")
        policies = [AuthorizationPolicyBuilder().with_permission(permission).build()]
        flow = FlowBuilder("my_field", self.content_type).with_transition(state1, state2, policies).build()

        function = Function.objects.create(name="noop-thread", body="def handle(context):\n    pass", is_approved=True)
        OnApprovedHook.objects.create(
            workflow=flow.workflow, callback_function=function, hook_type=BEFORE,
            transition_approval_meta=flow.transitions_approval_metas[0],
        )

        recorded = {}
        call_done = threading.Event()

        def _fake_execute_now(self, context):
            recorded["thread_name"] = threading.current_thread().name
            recorded["context"] = context
            call_done.set()

        with mock.patch.object(OnApprovedHook, "execute_now", _fake_execute_now):
            flow.objects[0].river.my_field.approve(as_user=user)
            # approve() itself must not block on the hook running - the
            # patched execute_now hasn't necessarily run yet right here.
            finished_in_time = call_done.wait(timeout=2)

        assert_that(finished_in_time, is_(True))
        assert_that(recorded["thread_name"].startswith("river-hook"), is_(True))
