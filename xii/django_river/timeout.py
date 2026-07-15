"""
Best-effort wall-clock timeout for ``river.Function`` execution.

See SECURITY.md: the sandbox (``RIVER_SANDBOX_DB_FUNCTIONS``) restricts *what*
a Function body can reach (no ``import``, no dunder-attribute escapes), but
never limited *how long* it can run - a ``while True: pass`` hangs the
request either way, sandboxed or not. ``RIVER_FUNCTION_TIMEOUT_SECONDS``
(unset/``None`` by default - this changes nothing unless configured) adds an
opt-in wall-clock limit independent of sandboxing.

Implementation note - please read before relying on this: it uses
``signal.alarm``, which only works in the main thread of the main
interpreter and only on platforms with ``SIGALRM`` (no Windows). When
neither is true (e.g. running inside ``thread_pool_executor``, see
``executors.py``, or under a WSGI server that handles requests on worker
threads), enforcement is silently *skipped* - not silently pretended to
work - and that's logged once at WARNING so it's visible instead of a false
sense of safety. A thread- or process-based timeout would work in more
places, but can't safely interrupt arbitrary C-level blocking calls either,
and forcibly killing a thread/process mid-way through in-progress ORM
writes trades one risk for another; ``signal.alarm`` is the least
surprising default for the common case (a synchronous Django request
handled on the main thread).
"""

import logging
import signal
import threading
from contextlib import contextmanager

LOGGER = logging.getLogger(__name__)

_warned_unsupported = False


class FunctionTimeoutError(Exception):
    """Raised when a river.Function body exceeds RIVER_FUNCTION_TIMEOUT_SECONDS."""


def _supports_alarm():
    return hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()


@contextmanager
def enforce_timeout(seconds, function_name=""):
    """
    No-op unless ``seconds`` is truthy. Raises ``FunctionTimeoutError`` if
    the wrapped block is still running after ``seconds`` - see the module
    docstring for the platform/thread limitations of how that's enforced.
    """
    global _warned_unsupported

    if not seconds:
        yield
        return

    if not _supports_alarm():
        if not _warned_unsupported:
            LOGGER.warning(
                "RIVER_FUNCTION_TIMEOUT_SECONDS=%s is set but this process can't "
                "enforce it here (needs SIGALRM support and the main thread); "
                "'%s' (and any other river.Function from here on, until this is "
                "fixed or the process restarts) will run without a timeout.",
                seconds, function_name,
            )
            _warned_unsupported = True
        yield
        return

    def _on_alarm(signum, frame):
        raise FunctionTimeoutError(
            "river.Function '%s' exceeded RIVER_FUNCTION_TIMEOUT_SECONDS=%s" % (function_name, seconds)
        )

    previous_handler = signal.signal(signal.SIGALRM, _on_alarm)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
