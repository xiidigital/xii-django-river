.. _hooking_guide:

Hook it Up
==========

The hookings in ``xii-django-river`` can be created both specifically for a workflow object or for a whole workflow. ``xii-django-river`` comes with some model objects and admin interfaces which you can use
to create the hooks.

* To create one for whole workflow regardless of what the workflow object is, go to

    * ``/admin/xii_django_river/onapprovedhook/`` to hook up to an approval
    * ``/admin/xii_django_river/ontransithook/`` to hook up to a transition
    * ``/admin/xii_django_river/oncompletehook/`` to hook up to the completion of the workflow

* To create one for a specific workflow object you should use the admin interface for the workflow object itself. One amazing feature of ``xii-django-river`` is now that
  it creates a default admin interface with the hookings for your workflow model class. If you have already defined one, ``xii-django-river`` enriches your already defined
  admin with the hooking section. It is default disabled. To enable it just define ``RIVER_INJECT_MODEL_ADMIN`` to be ``True`` in the ``settings.py``.


**Note:** They can programmatically be created as well since they are model objects. If it is needed to be at workflow level, just don't provide the workflow object column. If it is needed
to be for a specific workflow object then provide it.

Here are the list of hook models;

* OnApprovedHook
* OnTransitHook
* OnCompleteHook

.. note::
    (Fork-specific) Saving any of these hooks validates that its
    ``callback_function`` has been approved (``Function.is_approved``) —
    see :ref:`hooking_function_security_gates`. Attaching a hook to an
    unapproved ``Function`` raises ``ValidationError`` immediately, whether
    you're using the admin, a data migration, or plain ORM code, instead
    of silently never firing at runtime.

Runtime failures: ``RIVER_STRICT_HOOKS``
-----------------------------------------

By default (``RIVER_STRICT_HOOKS = False``), if a hook's callback raises
an exception while running, ``Hook.execute()`` catches it, logs it, and
lets the underlying transition succeed anyway — hooks are treated as
best-effort side effects that shouldn't be able to block the workflow
itself. Set ``RIVER_STRICT_HOOKS = True`` to make hook exceptions propagate
instead, failing the whole transition. See :ref:`security_guide` for how
to decide between the two: it comes down to whether you want a broken hook
(e.g. one authored by a tenant you don't control) to be able to block that
workflow's core transition, or not.
