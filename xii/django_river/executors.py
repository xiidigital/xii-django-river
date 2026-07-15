"""
Pluggable ``Hook`` execution.

By default (``RIVER_HOOK_EXECUTOR`` unset) hooks run synchronously, inline,
in whatever thread/request called ``Hook.execute()`` - exactly as before
this module existed. Nothing changes unless you configure it.

Set ``RIVER_HOOK_EXECUTOR`` to a dotted path to a callable
``executor(hook, context)`` to change *how* hooks run. That callable is
responsible for eventually calling ``hook.execute_now(context)`` - possibly
from a different thread, process, or worker, at its own discretion.

What an executor must NOT assume: ``context["hook"]["payload"]`` holds live
Django model instances (``workflow_object``, ``transition_approval``,
``workflow``), not primitives. A same-process executor (like
``thread_pool_executor`` below) can pass those straight through. A
process-boundary executor (Celery, RQ, an HTTP webhook, ...) cannot pickle
them across that boundary as-is - write a task that takes
``(content_type_id, object_id, field_name, transition_approval_id)`` (or
whatever subset it needs), re-fetches the real objects inside the worker,
rebuilds an equivalent context dict, and calls ``hook.execute_now(...)``
there. See docs/hooking/hooking.rst for a worked Celery example.

What every executor gives up, by construction, versus the synchronous
default: ``RIVER_STRICT_HOOKS``'s guarantee that a hook exception propagates
and fails the transition only holds for the synchronous default. Once a
hook runs off-thread or out-of-process, there is no calling stack left to
propagate an exception into - the transition has already been saved and
returned to the caller. Async executors must surface hook failures through
their own channel (logging, a dead-letter queue, monitoring, ...), not by
raising back into the original request.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

LOGGER = logging.getLogger(__name__)

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(thread_name_prefix="river-hook")
    return _pool


def thread_pool_executor(hook, context):
    """
    Ready-to-use, same-process executor: moves ``hook.execute_now(context)``
    onto a shared background thread pool instead of running it inline. That
    is enough to stop a slow hook (an HTTP call, an email send) from
    blocking the request/response cycle, with no extra infrastructure.

    What it does NOT give you: durability. If the process crashes between
    scheduling the hook and it actually running, the hook is lost - there is
    no persisted queue behind this, just an in-memory thread pool. For that,
    write your own executor around whatever real queue (Celery, RQ, ...)
    this project already uses, following the contract in this module's
    docstring.

    Also note (see xii/django_river/timeout.py): ``RIVER_FUNCTION_TIMEOUT_SECONDS``
    is enforced with ``signal.alarm``, which only works on the main thread.
    Hooks run through this executor execute on a worker thread, so that
    timeout can't apply here either - a hung hook body will hang the worker
    thread (and any callback function reuse tied to it), quietly, without
    blocking the request that triggered it.
    """

    def _run():
        try:
            hook.execute_now(context)
        except Exception:
            LOGGER.exception("Unhandled exception running hook %s off-thread.", hook.pk)

    _get_pool().submit(_run)
