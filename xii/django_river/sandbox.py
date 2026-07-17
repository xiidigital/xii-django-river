"""
Optional execution sandbox for ``river.Function`` bodies, built on
RestrictedPython. See SECURITY.md for the full threat model this addresses
and — just as importantly — what it does not address (no CPU/memory/time
limits, no protection against a DB role that can reach other schemas).

This module is only imported when ``RIVER_SANDBOX_DB_FUNCTIONS = True``
(xii/django_river/config.py), so RestrictedPython stays an optional dependency
(``pip install xii-django-river[sandbox]``) for projects that don't need it.
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
        safer_getattr,
    )
    from RestrictedPython.PrintCollector import PrintCollector

    RESTRICTED_PYTHON_AVAILABLE = True
except ImportError:
    RESTRICTED_PYTHON_AVAILABLE = False


def _build_restricted_globals():
    # `_getattr_` is `RestrictedPython.Guards.safer_getattr`, NOT the plain
    # builtin `getattr`. The compiler-level guard (rejecting any *source-level*
    # attribute name starting with "_", e.g. `().__class__`) only blocks a
    # dunder lookup spelled directly in the body's source - it does nothing
    # about a dunder name assembled at runtime and handed to `getattr`
    # indirectly, which is exactly what `str.format` does internally:
    # `"{0.__class__}".format(context)` reaches `__class__` via CPython's own
    # C-level attribute lookup inside `format()`, never touching the AST
    # transform that blocks source-level dunders. `safer_getattr` closes that
    # gap by rejecting any name starting with "_" *at call time*, regardless
    # of how the name was constructed - so this still fails even via
    # `str.format`, `getattr(obj, computed_name)`, etc. `__builtins__` is
    # replaced wholesale with `safe_builtins` (no `open`, `__import__`,
    # `eval`, `exec`, `compile`, ...), so there is no path to the filesystem,
    # network, or another `exec` from inside the body either.
    return {
        "__builtins__": dict(safe_builtins),
        "_getattr_": safer_getattr,
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
            "installed. Install it with `pip install xii-django-river[sandbox]`."
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
