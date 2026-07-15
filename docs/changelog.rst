.. _change_logs:

Change Logs
===========

4.0.0 (this fork):
------------------
    * **Improvement**  -  Modernized for current Django (``4.2``–``6.0``) and Python (``3.10``–``3.13``); Django ``6.0`` requires Python ``>=3.12``.
    * **Drop**          -  ``django-mptt`` dependency removed (it was never actually used as a tree).
    * **Improvement**  -  ``django-cte`` bumped to ``>=3.0``; ``django-codemirror2`` is now optional (``pip install xii-django-river[codemirror]``).
    * **Improvement**  -  SQL Server support rewritten on top of ``mssql-django`` (``pip install xii-django-river[mssql]``) with a fully parametrized query, replacing the old ``sql_server.pyodbc``-based driver.
    * **Bug**           -  The public signals (``pre_approve``, ``post_approve``, ``pre_transition``, ``post_transition``, ``pre_on_complete``, ``post_on_complete``) were declared but never emitted. They're now actually sent from the relevant context managers; ``post_*`` signals fire only when no exception occurred.
    * **Bug**           -  ``Function.get()``'s cache was read by ``self.name`` but written by ``self.pk``, so it never hit and recompiled the body with ``exec()`` on every single hook execution. Fixed to cache correctly by key, validating ``version``/``body``.
    * **Security**      -  New setting ``RIVER_ALLOW_DB_FUNCTIONS`` (default ``False``): ``Function.get()`` refuses to execute anything unless explicitly enabled. Deliberate breaking change for anyone already using DB-stored hooks — they must opt in.
    * **Security**      -  ``Function`` review workflow: ``is_approved`` field (reset whenever the body is edited), ``xii_django_river.approve_function`` / ``xii_django_river.self_approve_function`` permissions, and an immutable ``FunctionRevision`` audit trail (diff, who, when, plus a ``changed_by_username`` snapshot that survives account deletion).
    * **Security**      -  ``Hook.save()`` now rejects (``ValidationError``) attaching a hook to an unapproved ``Function`` at configuration time, instead of the hook silently never firing at runtime.
    * **Security**      -  Optional execution sandbox: new setting ``RIVER_SANDBOX_DB_FUNCTIONS`` (default ``False``, ``pip install xii-django-river[sandbox]``) compiles ``Function`` bodies with `RestrictedPython <https://restrictedpython.readthedocs.io/>`_ instead of plain ``exec()``, blocking ``import`` and dunder-attribute sandbox escapes.
    * **Bug**           -  ``Function.get()``'s process-wide compiled-function cache could serve one tenant a function body compiled for another tenant's ``Function`` with the same primary key, under schema-per-tenant multitenancy. Cache key now includes the connection's schema name.
    * **Improvement**  -  New setting ``RIVER_STRICT_HOOKS`` (default ``False``): when ``True``, exceptions raised by hooks propagate and fail the transition instead of being swallowed and logged.
    * **Docs**          -  New :ref:`security_guide` page documenting the full threat model, what is and isn't covered by the mitigations above, and how to decide ``RIVER_STRICT_HOOKS`` and permission grants depending on who is trusted to author hooks (single team vs. platform-supervised multi-tenant vs. fully autonomous multi-tenant).
    * **Bug**           -  ``RiverObject.__getattr__`` raised a bare ``Exception`` instead of ``AttributeError``, breaking ``hasattr()``, ``copy``, ``pickle`` and introspection on models with a ``StateField``.
    * **Improvement**  -  ``WorkflowRegistry`` now indexes by the class itself instead of ``id(cls)`` (fragile under the dev server's autoreload, since ids get recycled after GC).
    * **Improvement**  -  ``RiverConfig`` now reads settings on every access instead of caching them forever, so ``override_settings`` and other dynamic changes are respected in tests and at runtime.
    * **Bug**           -  ``RiverApp.ready()`` querying the database at startup (a ``RuntimeWarning`` on Django 5+) moved to a proper system check (``xii_django_river.W001``).
    * **Improvement**  -  Unified ``object_id`` to ``CharField(200)`` across ``Transition``/``TransitionApproval`` and hook models, with composite ``(content_type, object_id)`` indexes to avoid full scans on object lookups.
    * **Improvement**  -  Performance: ``prefetch_related`` in ``initialize_approvals``/``_re_create_cycled_path`` to remove N+1s, bulk ``update()`` in ``jump_to``, ``exists()`` instead of repeated ``count()`` calls.
    * **Infra**         -  ``pyproject.toml`` replaces legacy ``setup.py``/``setup.cfg``; GitHub Actions CI (matrix across supported Python/Django versions, missing-migrations check, full test run) replaces the dead Travis config.
    * **Tests**         -  Removed long-skipped legacy migration tests and a test suite that wrote migrations at runtime; suite is 69 tests, 0 skips.
    * **Breaking**      -  The importable package moved from ``river`` to ``xii.django_river`` and the Django ``app_label`` changed from ``river`` to ``xii_django_river``. Anyone upgrading an existing installation must follow :doc:`migration/migration_river_to_xii_django_river` before switching ``INSTALLED_APPS`` over.
    * **Infra**         -  Migrations squashed to a single ``0001_initial`` (the 6 inherited migrations were schema-only, no data migrations, so this is equivalent to their accumulated result). Fresh installs apply everything in one step; upgraders from the old ``river`` app_label follow the same migration guide as above.
    * **Feature**       -  New setting ``RIVER_FUNCTION_TIMEOUT_SECONDS`` (default ``None``/disabled): opt-in wall-clock timeout for ``Function`` execution, raising ``xii.django_river.timeout.FunctionTimeoutError``. Enforced with ``signal.alarm`` — see :ref:`security_guide` for the main-thread/platform limits of that approach.
    * **Feature**       -  New setting ``RIVER_HOOK_EXECUTOR`` (default ``None``/synchronous inline): pluggable ``Hook`` execution. Ships with ``xii.django_river.executors.thread_pool_executor`` (same-process background thread, no new infrastructure); anything else (Celery, RQ, ...) is a small adapter away following the contract in ``xii/django_river/executors.py``.
    * **Feature**       -  New model ``TransitionAuditLog``: an immutable, append-only record of every APPROVED/CANCELLED/JUMPED event on a workflow object (actor, timestamp), read-only in the admin. Complements ``TransitionApproval``, whose rows are mutated in place. ``InstanceWorkflowObject.jump_to()`` gained an optional ``as_user=None`` parameter to attribute jumps when the caller has one.
    * **Feature**       -  New system check ``check_workflow_configuration`` (``xii_django_river.W002``/``W003``/``W004``): flags transitions with no authorization rule at all or one with neither permissions nor groups (approvable by any authenticated user, per ``OrmDriver._authorized_approvals``), and orphaned states unused by any transition or workflow.
    * **Bug**           -  Hooks registered at the workflow level (no specific object) were matched by a free-text ``Workflow.field_name`` comparison instead of the exact ``Workflow`` row, so two unrelated models naming their ``StateField`` the same (``status`` is common) leaked each other's hooks — worst case for ``OnCompleteHook``, which has no other field to narrow the match back down. Fixed in all three signal context managers.
    * **Bug**           -  Deleting a workflow object that had ever had an approved transition crashed unconditionally with ``ProtectedError`` instead of deleting cleanly: the ``<field>_transitions``/``<field>_transition_approvals`` ``GenericRelation``\ s cascade-delete ``Transition``/``TransitionApproval`` rows on object deletion, but ``TransitionApproval.transition`` was ``on_delete=PROTECT``, so the deletion collector found a ``Transition`` it was cascading away still "protected" by a ``TransitionApproval`` being cascaded away in the same operation. Changed to ``CASCADE`` (migration ``0003``); nothing in this codebase ever deleted a ``Transition`` outside that exact cascade path.
    * **Improvement**  -  Removed several redundant queries (``Workflow``/``ContentType`` re-fetched by the signal classes when the caller already had them, ``ClassWorkflowObject.initial_state``, ``TransitionApprovalMeta.post_save_model``, a double-evaluated ``recent_approval`` in ``jump_to``) and fixed a real bug in ``create_function()`` that crashed with ``IntegrityError`` when re-registering a callback whose source body had changed.
    * **Security**      -  ``MsSqlDriver`` now resolves permissions through ``auth.get_backends()`` like ``OrmDriver`` already did, instead of only ``user_permissions``/group-assigned permissions — closing a gap where a user authorized solely via a custom auth backend was denied approvals on SQL Server but not on other databases.

    See ``TECH_DEBT.md`` and ``SECURITY.md`` (or :ref:`security_guide`) in the repository for the full rationale and trade-offs behind the security-related items above.

3.3.0 (Stable) and earlier: upstream django-river releases
------------------------------------------------------------
Everything from here down (``3.3.0`` and earlier) is inherited, unmodified, from
the original `django-river <https://github.com/javrasya/django-river>`_ project's
own changelog, predating this fork.

3.3.0 (Stable):
---------------
    * **Drop**         -  # 182_: No longer maintain Python versions <= 3.5
    * **Drop**         -  # 181_: No longer maintain Django versions <= 2.1

.. _181: https://github.com/javrasya/django-river/issues/181
.. _182: https://github.com/javrasya/django-river/issues/182

3.2.2:
------
    * **Bug**         -  # 162_: Fix a bug that is causing some possible future transitions to turn to CANCELLED for some workflows.

.. _162: https://github.com/javrasya/django-river/issues/159

3.2.1:
------
    * **Bug**         -  # 159_: A bug that is with having multiple cyclic dependencies in a workflow that happens when one of tem goes through has been fixed.
    * **Drop**        -        : Drop Python3.4 support since it is having incompatibilities with the module ``six``


.. _159: https://github.com/javrasya/django-river/issues/159

3.2.0:
------
    * **Improvement** -  # 140_ 141_: Support Microsoft SQL Server 17 and 19


.. _140: https://github.com/javrasya/django-river/issues/140
.. _141: https://github.com/javrasya/django-river/issues/141

3.1.4:
------
    * **Bug**         -  # 137_: Fix a bug with jumping to a state


.. _137: https://github.com/javrasya/django-river/issues/137

3.1.3:
------
    * **Improvement** -  # 135_: Support Django 3.0


.. _135: https://github.com/javrasya/django-river/issues/135


3.1.2:
------
    * **Improvement** -  # 133_: Support MySQL 8.0


.. _133: https://github.com/javrasya/django-river/issues/133

3.1.1
-----
    * **Bug**         -  # 128_: Available approvals are not found properly when primary key is string
    * **Bug**         -  # 129_: Models with string typed primary keys violates integer field in the hooks


.. _128: https://github.com/javrasya/django-river/issues/128
.. _129: https://github.com/javrasya/django-river/issues/129

3.1.0
-----
    * **Imrovement**  -  # 123_: Jump to a specific future state of a workflow object
    * **Bug**         -  # 124_: Include some BDD tests for the users to understand the usages easier.


.. _123: https://github.com/javrasya/django-river/issues/123
.. _124: https://github.com/javrasya/django-river/issues/124

3.0.0
-----
    * **Bug**         -  # 106_: It crashes when saving a workflow object when there is no workflow definition for a state field
    * **Bug**         -  # 107_: next_approvals api of the instance is broken
    * **Bug**         -  # 112_: Next approval after it cycles doesn't break the workflow anymore. Multiple cycles are working just fine.
    * **Improvement** -  # 108_: Status column of transition approvals are now kept as string in the DB instead of number to maintain readability and avoid mistakenly changed ordinals.
    * **Improvement** -  # 109_: Cancel all other peer approvals that are with different branching state.
    * **Improvement** -  # 110_: Introduce an iteration to keep track of the order of the transitions even the cycling ones. This comes with a migration that will assess the iteration of all of your existing approvals so far. According to the tests, 250 workflow objects that have 5 approvals each will take ~1 minutes with the slowest django `v1.11`.
    * **Improvement** -  # 111_: Cancel all approvals that are not part of the possible future instead of only impossible the peers when something approved and re-create the whole rest of the pipeline when it cycles
    * **Improvement** -  # 105_: More dynamic and better way for hooks.On the fly function and hook creations, update or delete are also supported now. It also comes with useful admin interfaces for hooks and functions. This is a huge improvement for callback lovers :-)
    * **Improvement** -  # 113_: Support defining an approval hook with a specific approval.
    * **Improvement** -  # 114_: Support defining a transition hook with a specific iteration.
    * **Drop** -         # 115_: Drop skipping and disabling approvals to cut the unnecessary complexity.
    * **Improvement** -  # 116_: Allow creating transitions without any approvals. A new TransitionMeta and Transition models are introduced to keep transition information even though there is no transition approval yet.


.. _105: https://github.com/javrasya/django-river/issues/105
.. _106: https://github.com/javrasya/django-river/issues/106
.. _107: https://github.com/javrasya/django-river/issues/107
.. _108: https://github.com/javrasya/django-river/issues/108
.. _109: https://github.com/javrasya/django-river/issues/109
.. _110: https://github.com/javrasya/django-river/issues/110
.. _111: https://github.com/javrasya/django-river/issues/110
.. _112: https://github.com/javrasya/django-river/issues/112
.. _113: https://github.com/javrasya/django-river/issues/113
.. _114: https://github.com/javrasya/django-river/issues/114
.. _115: https://github.com/javrasya/django-river/issues/115
.. _116: https://github.com/javrasya/django-river/issues/116

2.0.0
-----
    * **Improvement** -  [ # 90_,# 36_ ]: Finding available approvals has been speeded up ~x400 times at scale
    * **Improvement** -  # 92_ : It is mandatory to provide initial state by the system user to avoid confusion and possible mistakes
    * **Improvement** -  # 93_ : Tests are revisited, separated, simplified and easy to maintain right now
    * **Improvement** -  # 94_ : Support class level hooking. Meaning that, a hook can be registered for all the objects through the class api
    * **Bug** -  # 91_ : Callbacks get removed when the related workflow object is deleted
    * **Improvement** -  Whole ``django-river`` source code is revisited and simplified
    * **Improvement** -  Support ``Django v2.2``
    * **Deprecation** -  ``Django v1.7``, ``v1.8``, ``v1.9`` and ``v1.10`` supports have been dropped

.. _36: https://github.com/javrasya/django-river/issues/36
.. _90: https://github.com/javrasya/django-river/issues/90
.. _91: https://github.com/javrasya/django-river/issues/91
.. _92: https://github.com/javrasya/django-river/issues/92
.. _93: https://github.com/javrasya/django-river/issues/93
.. _94: https://github.com/javrasya/django-river/issues/94

1.0.2
-----
    * **Bug** - # 77_ : Migrations for the models that have state field is no longer kept getting recreated.
    * **Bug** - It is crashing when there is no workflow in the workspace.

.. _77: https://github.com/javrasya/django-river/issues/77


1.0.1
-----
    * **Bug** - # 74_ : Fields that have no transition approval meta are now logged correctly.
    * **Bug** - ``django`` version is now fixed to 2.1 for coverage in the build to make the build pass

.. _74: https://github.com/javrasya/django-river/issues/74

1.0.0
-----
``django-river`` is finally having it's first major version bump. In this version, all code and the APIs are revisited
and are much easier to understand how it works and much easier to use it now. In some places even more performant. 
There are also more documentation with this version. Stay tuned :-)

    * **Improvement** - Support ``Django2.1``
    * **Improvement** - Support multiple state fields in a model
    * **Improvement** - Make the API very easy and useful by accessing everything via model objects and model classes
    * **Improvement** - Simplify the concepts
    * **Improvement** - Migrate ProceedingMeta and Transition into TransitionApprovalMeta for simplification
    * **Improvement** - Rename Proceeding as TransitionApproval
    * **Improvement** - Document transition and on-complete hooks
    * **Improvement** - Document transition and on-complete hooks
    * **Improvement** - Imrove documents in general
    * **Improvement** - Minor improvements on admin pages
    * **Improvement** - Some performance improvements

0.10.0
------

    * # 39_ - **Improvement** -  Django has dropped support for pypy-3. So, It should be dropped from django itself too.
    * **Remove** -  ``pypy`` support has been dropped
    * **Remove** -  ``Python3.3`` support has been dropped
    * **Improvement** - ``Django2.0`` support with ``Python3.5`` and ``Python3.6`` is provided

.. _39: https://github.com/javrasya/django-river/issues/39

0.9.0
-----

    * # 30_ - **Bug** -  Missing migration file which is ``0007`` because of ``Python2.7`` can not detect it.
    * # 31_ - **Improvement** - unicode issue for Python3.
    * # 33_ - **Bug** - Automatically injecting workflow manager was causing the models not have default ``objects`` one. So, automatic injection support has been dropped. If anyone want to use it, it can be used explicitly.
    * # 35_ - **Bug** - This is huge change in django-river. Multiple state field each model support is dropped completely and so many APIs have been changed. Check documentations and apply changes.

.. _30: https://github.com/javrasya/django-river/pull/30  
.. _31: https://github.com/javrasya/django-river/pull/30
.. _33: https://github.com/javrasya/django-river/pull/33
.. _35: https://github.com/javrasya/django-river/pull/35

0.8.2
-----

    * **Bug** - Features providing multiple state field in a model was causing a problem. When there are multiple state field, injected attributes in model class are owerriten. This feature is also unpractical. So, it is dropped to fix the bug.
    * **Improvement** - Initial video tutorial which is Simple jira example is added into the documentations. Also repository link of fakejira project which is created in the video tutorial is added into the docs.
    * **Improvement** - No proceeding meta parent input is required by user. It is set automatically by django-river now. The field is removed from ProceedingMeta admin interface too.


0.8.1
-----

    * **Bug** - ProceedingMeta form was causing a problem on migrations. Accessing content type before migrations was the problem. This is fixed by defining choices in init function instead of in field

0.8.0
-----

    * **Deprecation** - ProceedingTrack is removed. ProceedingTracks were being used to keep any transaction track to handle even circular one. This was a workaround. So, it can be handled with Proceeding now by cloning them if there is circle. ProceedingTracks was just causing confusion. To fix this, ProceedingTrack model and its functions are removed from django-river.
    * **Improvement** - Circular scenario test is added.
    * **Improvement** - Admins of the workflow components such as State, Transition and ProceedingMeta are registered automatically now. Issue #14 is fixed.

0.7.0
-----

    * **Improvement** - Python version 3.5 support is added. (not for Django1.7)
    * **Improvement** - Django version 1.9 support is added. (not for Python3.3 and PyPy3) 

0.6.2
-----

    * **Bug** - Migration ``0002`` and ``0003`` were not working properly for postgresql (maybe oracle). For these databases, data can not be fixed. Because, django migrates each in a transactional block and schema migration and data migration can not be done in a transactional block. To fix this, data fixing and schema fixing are seperated.
    * **Improvement** - Timeline section is added into documentation.
    * **Improvement** - State slug field is set as slug version of its label if it is not given on saving.


0.6.1
-----

    * **Bug** - After ``content_type`` and ``field`` are moved into ``ProceedingMeta`` model from ``Transition`` model in version ``0.6.0``, finding initial and final states was failing. This is fixed.
    * **Bug** - ``0002`` migrations was trying to set default slug field of State model. There was a unique problem. It is fixed. ``0002`` can be migrated now.
    * **Improvement** - The way of finding initial and final states is changed. ProceedingMeta now has parent-child tree structure to present state machine. This tree structure is used to define the way. This requires to migrate ``0003``. This migration will build the tree of your existed ProceedingMeta data.

0.6.0
-----

    * **Improvement** - ``content_type`` and ``field`` are moved into ``ProceedingMeta`` model from ``Transition`` model. This requires to migrate ``0002``. This migrations will move value of the fields from ``Transition`` to ``ProceedingMeta``.
    * **Improvement** - Slug field is added in ``State``. It is unique field to describe state. This requires to migrate ``0002``. This migration will set the field as slug version of ``label`` field value. (Re Opened -> re-opened)
    * **Improvement** - ``State`` model now has ``natural_key`` as ``slug`` field.
    * **Improvement** - ``Transition`` model now has ``natural_key`` as (``source_state_slug`` , ``destination_state_slug``) fields
    * **Improvement** - ``ProceedingMeta`` model now has ``natural_key`` as (``content_type``, ``field``, ``transition``, ``order``) fields
    * **Improvement** - Changelog is added into documentation.
  

0.5.3
-----

    * **Bug** - Authorization was not working properly when the user has irrelevant permissions and groups. This is fixed.
    * **Improvement** - User permissions are now retreived from registered authentication backends instead of ``user.user_permissions``
  

0.5.2
-----

    * **Improvement** - Removed unnecessary models.
    * **Improvement** - Migrations are added
    * **Bug** - ``content_type__0002`` migrations cause failing for ``django1.7``. Dependency is removed
    * **Bug** - ``DatabaseHandlerBacked`` was trying to access database on django setup. This cause ``no table in db`` error for some django commands. This was happening; because there is no db created before some commands are executed; like ``makemigrations``, ``migrate``.


0.5.1
-----

    * **Improvement** - Example scenario diagrams are added into documentation.
    * **Bug** - Migrations was failing because of injected ``ProceedingTrack`` relation. Relation is not injected anymore. But property ``proceeing_track`` remains. It still returns current one.
