# Security notes: `xii_django_river.Function` and DB-stored hooks

`xii_django_river.Function` stores a Python function body as text in the database and
runs it with `exec()` (`xii/django_river/models/function.py`). This is a deliberate
design feature — hooks can be changed without a deploy — but it means
**anyone who can write to the `Function` table can execute arbitrary code
in the same process as the rest of the application.** This document exists
so any project embedding this fork can reason about the risk explicitly,
instead of discovering it in production.

This fork does not assume a particular deployment shape (single tenant,
multi-tenant with a platform operator, multi-tenant with fully autonomous
tenants). The mitigations below are mechanisms — settings and permissions —
that let the *consuming project* pick the policy that matches its own
threat model. Nothing here is specific to any one deployment.

## What this fork already does

- **`RIVER_ALLOW_DB_FUNCTIONS`** (default `False`). `Function.get()` refuses
  to execute anything unless this is set. It exists so that adopting a
  version of `xii-django-river` with DB-stored hooks is an explicit, conscious choice
  by whoever configures the project, not a silent default.

- **Per-`Function` approval gate.** Independent of the setting above,
  each `Function` row has `is_approved` (default `False`). `Function.get()`
  refuses to run unapproved code even when `RIVER_ALLOW_DB_FUNCTIONS=True`.
  Editing the `body` resets `is_approved` — a reviewer must sign off on the
  new code, not the old one.

- **Two separate permissions**, so "who can review" is configurable per
  deployment:
  - `xii_django_river.approve_function` — required to use the "Approve selected
    functions" admin action at all.
  - `xii_django_river.self_approve_function` — required, *in addition to the above*,
    for the author of a `Function`'s last edit to approve their own change.
    Without it, `Function.approve()` raises `ImproperlyConfigured` when
    `approver == updated_by`.

  A project with a platform operator reviewing tenant-authored hooks would
  grant `approve_function` only to operator staff, and never grant
  `self_approve_function` to tenants. A project with fully autonomous
  tenants (no external reviewer — see "Threat models" below) would instead
  grant both permissions to each tenant's own admin/owner user, so they can
  self-serve without anyone else in the loop.

- **Immutable audit trail (`FunctionRevision`)**. Every time a `Function`'s
  body is created or edited, a row is written with a diff against the
  previous version, who changed it, and when. Every `approve()` call writes
  its own row, tagged `APPROVED` or `SELF_APPROVED` depending on whether the
  approver is the author — so self-approval is always visible in history,
  never indistinguishable from a second-reviewer approval. Reachable from
  the Django admin as a read-only inline on `Function` (nobody, including
  superusers, can edit or delete past revisions from the UI).

- **Per-schema cache isolation.** `Function.get()` caches the compiled
  callable in a process-wide dict. Under schema-per-tenant multitenancy,
  tenants' `Function` tables restart their PK sequence independently, so a
  cache keyed only by `pk` could serve Tenant B a stale compiled function
  that actually belongs to Tenant A's `Function #1` (or vice versa). The
  cache key now includes `connection.schema_name` (`Function._cache_key()`)
  to prevent this.

- **`create_function(callback)` auto-approves.** This helper registers a
  plain Python function *defined in your codebase* as a `Function` row
  (`Hook.callback_function` is a mandatory FK to `Function`, so hooks
  written as normal reviewed code still need a row). Since the body comes
  from source that already went through your normal review process (PR,
  CI, etc.), there is nothing left for a `Function`-level reviewer to sign
  off on, so these rows are approved automatically on creation.

- **`Hook.save()` rejects unapproved `Function`s at configuration time.**
  Attaching a `Hook` to a `Function` that isn't approved raises
  `ValidationError` immediately — in the admin, in a data migration, or
  from plain ORM code. This turns "the hook silently never runs because
  its Function isn't approved" from a runtime mystery (previously only
  visible in logs, and only then if `RIVER_STRICT_HOOKS=True`) into an
  immediate, explicit configuration error. This only covers the moment the
  `Hook` is saved, though — editing that `Function`'s body afterwards
  resets `is_approved` (see `on_pre_save` above) without touching any
  `Hook` that already points to it, leaving it silently pointing at code
  that is no longer approved. System check **`xii_django_river.W005`**
  (`RiverApp.ready()` / `check_hooks_with_unapproved_functions`) surfaces
  exactly that case ahead of time, since `Hook.execute()` will still refuse
  to run it at that point but nothing else would tell you until it does.

- **Optional execution sandbox (`RIVER_SANDBOX_DB_FUNCTIONS`, default
  `False`)**. When enabled (`pip install xii-django-river[sandbox]`),
  `Function` bodies compile through
  [RestrictedPython](https://restrictedpython.readthedocs.io/) instead of
  plain `exec()`: no `import` statements resolve (no `__import__` in the
  restricted builtins), no dunder attribute access *spelled directly in the
  source* compiles at all (blocks the classic
  `().__class__.__bases__[0].__subclasses__()` sandbox escape at the source
  level, before it would even run), attribute access at runtime goes through
  `RestrictedPython.Guards.safer_getattr` (rejects any attribute name
  starting with `_` at call time, regardless of how that name was
  constructed — this additionally blocks *indirect* dunder access, e.g.
  `"{0.__class__}".format(context)`, which reaches `__class__` through
  `str.format`'s own C-level attribute lookup and would otherwise never
  touch the source-level dunder check at all), and `__builtins__` is
  replaced with RestrictedPython's `safe_builtins` (no `open`, `eval`,
  `exec`, `compile`, `__import__`). See `xii/django_river/sandbox.py`. This is opt-in
  and not fully backward compatible — bodies that rely on `import` or on
  reaching things outside the `context` argument will need rewriting — see
  "What this still does NOT do" for what it doesn't cover even when on.

- **Audit trail survives account deletion.** `FunctionRevision` stores a
  denormalized `changed_by_username` snapshot at write time, in addition to
  the `changed_by` FK (which is `on_delete=SET_NULL`). If the account is
  later deleted, the FK goes `NULL` but the snapshot stays, so "who did
  this" remains answerable.

- **Opt-in wall-clock timeout (`RIVER_FUNCTION_TIMEOUT_SECONDS`, default
  `None`/disabled).** Bounds how long a `Function` body can run before
  `Function.get()`'s returned callable raises
  `xii.django_river.timeout.FunctionTimeoutError` — independent of, and
  layered on top of, the sandbox: a sandboxed body still can't `import`, but
  nothing stopped `while True: pass` before this. Read
  `xii/django_river/timeout.py`'s module docstring before relying on it:
  it's enforced with `signal.alarm`, which only works in the main thread of
  the main interpreter (no Windows, no worker threads — including this
  fork's own `thread_pool_executor`, see below). When it can't be enforced,
  that's logged once at WARNING rather than silently doing nothing.

- **Pluggable hook execution (`RIVER_HOOK_EXECUTOR`, default `None` /
  synchronous inline, unchanged).** `Hook.execute()` dispatches to a
  configured executor instead of running inline when set — see
  `xii/django_river/executors.py`. Ships with `thread_pool_executor`
  (moves execution to a shared background thread, same process, no new
  infrastructure) as a ready-to-use option; anything else (Celery, RQ, ...)
  is one small adapter function away, following the documented contract.
  Trade-off, stated plainly: `RIVER_STRICT_HOOKS`'s guarantee that a hook
  exception fails the transition only holds for the synchronous default —
  once a hook runs off-thread/off-process there is no call stack left to
  propagate into, by construction, for any executor.

- **Transition-level audit trail (`TransitionAuditLog`).** Every APPROVED,
  CANCELLED, and JUMPED event on a workflow object is appended (never
  updated in place, unlike `TransitionApproval`) with who did it (when
  there is a "who" — `jump_to`'s actor is optional) and when. Read-only in
  the admin, like `FunctionRevision`.

Test coverage: `xii/django_river/tests/test__function_gate.py`,
`xii/django_river/tests/test__function_approval.py`,
`xii/django_river/tests/test__hook_approval_gate.py`,
`xii/django_river/tests/test__function_sandbox.py`,
`xii/django_river/tests/test__function_timeout.py`,
`xii/django_river/tests/test__hook_executor.py`,
`xii/django_river/tests/test__transition_audit_log.py`.

## What this still does NOT do (open, by design — see "Threat models")

- **The sandbox is not a full isolation boundary.** Even with
  `RIVER_SANDBOX_DB_FUNCTIONS=True`, RestrictedPython doesn't limit CPU,
  memory, or wall-clock time (a `Function` can still loop forever or
  allocate unbounded memory — see "No resource limits" below), and
  RestrictedPython itself has had sandbox-escape CVEs historically. It
  meaningfully shrinks the blast radius (no filesystem, no network import,
  no dunder-based escape), but "meaningfully smaller" is not "zero."
  Whatever objects you choose to expose in a `Function`'s `context` are
  still reachable and their full (non-restricted) attribute surface is
  usable through them — the sandbox restricts the *body*'s own code, not
  what a passed-in object lets you do with `_getattr_`.

- **No database-level tenant isolation.** Nothing here restricts what
  schemas a `Function`'s code can reach via the ORM. If the DB role used by
  the app has grants across all tenant schemas (the common default with
  `django-tenants`, since schema isolation there is a `search_path`
  convention, not a Postgres permission boundary), then a `Function`'s code
  — sandboxed or not — can still be handed (via `context`) a live ORM
  manager or connection object that reaches `schema_context("other_tenant")`
  and read or write another tenant's data. Where the `Function` model is
  installed (shared vs. per-tenant app) only affects *who can see/author*
  the row; it does not affect what the code can reach once it executes.
  Real cross-tenant containment requires either a Postgres role per tenant
  with grants scoped to that tenant's schema only, or never passing
  ORM/connection objects into `context` for sandboxed Functions at all. This
  is infrastructure the consuming project owns, not something `xii-django-river` can
  implement from inside the ORM — see "DB role isolation per tenant" below
  for concrete steps.

- **No CPU/memory limits, and the wall-clock timeout has real gaps.**
  `RIVER_FUNCTION_TIMEOUT_SECONDS` (see above) bounds wall-clock time in the
  common case (synchronous request, main thread), but it enforces nothing
  on a worker thread (the built-in `thread_pool_executor` included) or a
  non-Unix platform, and it never limits CPU or memory — a body that
  allocates unbounded memory in a way that doesn't yield the GIL back to
  the alarm signal isn't stopped. For a real resource ceiling regardless of
  thread/platform, run hook execution in a separate worker process with
  `resource.setrlimit`, or a container-level limit (cgroups) around the
  worker process entirely — this fork can bound time on the common path, it
  cannot sandbox CPU/memory from inside the same process.

## DB role isolation per tenant: not this fork's job, but here's how to do it

Everything above is enforced from inside `xii-django-river` — it controls whether code
runs and who authorized it. It cannot control what a Postgres connection is
allowed to touch once that code is running, because `xii-django-river` is a Django app
installed into someone else's project: it doesn't own connection setup,
request routing, or how tenants get resolved. That part has to live in the
consuming project's infrastructure layer. This section is generic guidance
for whoever owns that layer, not a `xii-django-river` feature — nothing here requires
or assumes `xii-django-river` at all beyond "arbitrary code may run in this
connection."

**Why "put `Function` in a per-tenant schema" doesn't solve this by itself.**
Schema-per-tenant multitenancy (e.g. `django-tenants`) usually isolates
tenants by having every request `SET search_path` to the current tenant's
schema on a single shared Postgres role. That role typically has grants on
*every* tenant schema, because the same role serves every tenant depending
on which request comes in. `search_path` is a connection-level convention,
not a permission boundary — any code running in that connection, malicious
or not, can simply change it (or otherwise fully-qualify a table name) and
read or write a schema search_path didn't select. So the actual boundary
that needs enforcing is: **can this connection's role read/write schemas
other than the current tenant's, at the database permission level.**

**The realistic fix for schema-per-tenant Postgres: `SET LOCAL ROLE` per
request, not a separate physical connection per tenant.** Standing up a
distinct DB connection (with distinct credentials) for every tenant is
usually impractical with connection pooling at any real scale. The
pattern that works within that constraint:

1. Create one restricted Postgres role per tenant, with grants scoped to
   only that tenant's schema, and make your application's normal login role
   a member of every such role so it's *allowed* to switch into them:

   ```sql
   CREATE ROLE tenant_acme NOLOGIN;
   GRANT USAGE ON SCHEMA tenant_acme TO tenant_acme;
   GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA tenant_acme TO tenant_acme;
   ALTER DEFAULT PRIVILEGES IN SCHEMA tenant_acme
       GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO tenant_acme;
   GRANT tenant_acme TO app_login_role;  -- lets app_login_role "SET ROLE tenant_acme"
   ```

2. Wherever your framework resolves the current tenant and switches
   `search_path` (for `django-tenants`, its schema-switching middleware /
   connection wrapper), also issue `SET LOCAL ROLE tenant_<schema>` at the
   start of the request's transaction, and let it reset naturally at
   transaction end (`SET LOCAL` is transaction-scoped by design — this is
   what makes it safe to use with connection pooling, since it can't leak
   into the next request/transaction that reuses the physical connection).

3. Now even if a `Function`'s code calls `schema_context("other_tenant")`
   or otherwise tries to read/write a different schema's tables, the
   `GRANT`s on the active role reject it at the database — not because the
   application chose not to look there, but because Postgres itself won't
   let that role touch those tables.

**Caveats to plan for, honestly:**
- This adds real operational surface: a Postgres role per tenant, kept in
  sync with tenant creation/deletion, and `ALTER DEFAULT PRIVILEGES` kept
  correct as new tables get migrated in.
- `SET LOCAL ROLE` must be reissued every transaction — if any code path
  runs outside the transaction where it was set (background workers,
  connections pulled from a pool without going through the same
  request-start hook), it silently reverts to the broader login role's
  privileges. Async task processing (e.g. this project's own
  `django_q`-based pipeline pattern, if you have one) needs the same
  schema-switch-then-set-role treatment applied at the start of every task,
  not just at HTTP request start.
- With an external connection pooler in transaction-pooling mode (e.g.
  PgBouncer), verify `SET LOCAL` semantics still hold for your pooler
  configuration — some poolers interact poorly with session-level `SET`
  (as opposed to `SET LOCAL`, which is the one to use here specifically
  because it's transaction-scoped and pooler-safe by construction).
- This is independent of, and complementary to, `RIVER_SANDBOX_DB_FUNCTIONS`
  above: the sandbox restricts what a `Function`'s own code can directly
  express (no arbitrary `import`, no dunder escapes); the DB role restricts
  what any code running in that connection can reach, including through
  objects you deliberately expose via `context`. Neither substitutes for
  the other — sandboxing without DB role isolation still lets an exposed
  ORM object reach other schemas; DB role isolation without sandboxing
  still lets arbitrary code do damage within the tenant's own schema (read
  secrets passed into `context`, exhaust resources, etc).

## Threat models: what to configure depending on who authors `Function`s

**Trusted team, single tenant (or multi-tenant with a platform operator
reviewing every tenant's hooks).** The approval gate is a genuine second
pair of eyes: grant `approve_function` to operator staff, don't grant
`self_approve_function` to anyone outside that team. Sandboxing and DB role
isolation are defense in depth, not strictly required, since the same
people who could write malicious `Function` bodies already have broad
access to the system.

**Multi-tenant, tenants are fully autonomous (no platform reviewer sits
above them).** Here "someone reviews it" isn't available as a control —
there is no one to grant `approve_function` to except the tenant itself.
In this model, `self_approve_function` granted to each tenant's own
admin/owner is the correct policy (self-serve, no external approver), but
it only contains risk *within* that tenant if the two items in "What this
still does NOT do" above are actually addressed: turn on
`RIVER_SANDBOX_DB_FUNCTIONS` (so a tenant's code can't `import`, can't
escape via dunder attributes, and only has `safe_builtins`), keep
`context` free of live ORM/connection objects for these tenants, and add
DB role isolation (so even a successful `schema_context()` call — reached
some other way — fails at the database permission layer). Without those,
granting broad self-approval to tenants is closer to granting them RCE
against the shared process and, transitively, every other tenant in it —
the approval workflow alone governs authorization, not containment.

## `RIVER_STRICT_HOOKS`: how to decide

`Hook.execute()` catches every exception raised by a hook body (including
`ImproperlyConfigured` from an unapproved `Function`) and only logs it,
*unless* `RIVER_STRICT_HOOKS=True`, in which case the exception propagates
and the whole transition fails.

- **`False` (default).** Hooks behave as best-effort side effects: a
  broken or unapproved hook never blocks the underlying business
  transition (e.g. approving a workflow object still succeeds even if a
  notification hook throws). The cost is silence — an unapproved or
  misconfigured hook simply never runs, and nothing surfaces that fact
  unless someone is watching logs.
- **`True`.** Nothing fails silently — a broken or unapproved hook blocks
  the transition immediately, visible to whoever triggered it. The cost is
  fragility: any hook bug (including one authored by a tenant you don't
  control) can block that tenant's core workflow, not just its side
  effects.

`Hook.save()` already validates that `callback_function.is_approved` at
configuration time (see above), so "the function isn't approved yet" is
no longer part of this trade-off — that failure mode is rejected before a
`Hook` can even be saved. `RIVER_STRICT_HOOKS` is left to answer a
narrower, purely product-level question: should a *runtime* bug in
already-approved hook code block the transition, or not.

## Known limitation: `created_by`/`updated_by`/`approved_by` still go `NULL` on account deletion

`FunctionRevision.changed_by_username` (see above) keeps the audit trail
readable after an account is deleted, but the live pointer fields on
`Function` itself — `created_by`, `updated_by`, `approved_by` — are still
plain `on_delete=SET_NULL` FKs with no snapshot. So `Function.approved_by`
for a long-since-deleted reviewer will show `None` even though
`FunctionRevision.changed_by_username` for that same approval still says
who it was. If a project needs `Function`'s own fields (not just the
revision history) to survive account deletion, add the same
username-snapshot pattern there, or switch those FKs to `on_delete=PROTECT`
if blocking user deletion while they have authored/approved `Function`s is
acceptable.
