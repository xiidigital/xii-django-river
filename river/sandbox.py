"""
Optional execution sandbox for ``river.Function`` bodies, built on
RestrictedPython. See SECURITY.md for the full threat model this addresses
and — just as importantly — what it does not address (no CPU/memory/time
limits, no protection against a DB role that can reach other schemas).

This module is only imported when ``RIVER_SANDBOX_DB_FUNCTIONS = True``
(river/config.py), so RestrictedPython stays an optional dependency
(``pip install django-river[sandbox]``) for projects that don't need it.
"""

from django.core.exceptions import ImproperlyConfigured

try:
    from RestrictedPython import compile_restricted
    from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
    from RestrictedPython.Guards import (
        full_write_guard,
        guarded_iter_unpack_sequence,
        guarded_unpack_sequence,
        safe_builtins,
    )
    from RestrictedPython.PrintCollector import PrintCollector

    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False


def _build_restricted_globals():
    # `_getattr_` is intentionally the plain builtin `getattr`: RestrictedPython's
    # compiler already rejects any *source-level* attribute name starting with
    # "_" (the `().__class__.__bases__[0].__subclasses__()` escape and friends)
    # before this ever runs, so `handle()` simply cannot spell a dunder lookup
    # to begin with. `__builtins__` is replaced wholesale with `safe_builtins`
    # (no `open`, `__import__`, `eval`, `exec`, `compile`, ...), so there is no
    # path to the filesystem, network, or another `exec` from inside the body.
    return {
        "__builtins__": dict(safe_builtins),
        "_getattr_": getattr,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_write_": full_write_guard,
        "_print_": PrintCollector,
    }


def compile_sandboxed_handle(body):
    """
    Compiles a Function.body under RestrictedPython and returns the
    top-level `handle(context)` callable it defines. Raises whatever
    RestrictedPython/compile/exec raise on unsafe or invalid source
    (SyntaxError for statically-rejected constructs like `import` or dunder
    attribute access, NameError/ImportError if something tries to reach a
    builtin that isn't in the safe set at runtime) — callers (river's own
    Hook.execute, or whoever calls Function.get() directly) decide whether
    that propagates or gets swallowed, same as any other Function error.
    """
    if not RESTRICTED_PYTHON_AVAILABLE:
        raise ImproperlyConfigured(
            "RIVER_SANDBOX_DB_FUNCTIONS is enabled but RestrictedPython isn't "
            "installed. Install it with `pip install django-river[sandbox]`."
        )

    byte_code = compile_restricted(body, filename="<river.Function>", mode="exec")
    restricted_globals = _build_restricted_globals()
    local_namespace = {}
    exec(byte_code, restricted_globals, local_namespace)

    handle = local_namespace.get("handle")
    if handle is None or not callable(handle):
        raise ImproperlyConfigured(
            "A sandboxed river.Function body must define a top-level "
            "`def handle(context):` function."
        )
    return handle
