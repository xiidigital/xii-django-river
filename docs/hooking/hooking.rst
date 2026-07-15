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

Running hooks off the request thread: ``RIVER_HOOK_EXECUTOR``
-----------------------------------------------------------------

(Fork-specific.) By default hooks run synchronously, inline, in whatever
thread called ``approve()``/``jump_to()`` — a slow hook (an HTTP call, an
email send) blocks the request until it finishes. Set
``RIVER_HOOK_EXECUTOR`` to a dotted path to a callable ``executor(hook,
context)`` to change that; it's responsible for eventually calling
``hook.execute_now(context)`` itself, possibly from a different thread,
process, or worker.

The simplest option, included and ready to use, needs no extra
infrastructure:

.. code:: python

    RIVER_HOOK_EXECUTOR = "xii.django_river.executors.thread_pool_executor"

This moves ``execute_now`` onto a shared background thread in the same
process. It is not durable — if the process crashes between scheduling and
running the hook, the hook is lost, since there's no persisted queue behind
it, just an in-memory thread pool.

For a real queue (Celery, RQ, ...), write a small adapter. The one thing to
get right: ``context["hook"]["payload"]`` holds live Django model instances
(``workflow_object``, ``transition_approval``, ``workflow``), not
primitives — a process-boundary executor can't pickle them across that
boundary as-is. Have the adapter pass identifying IDs into the task and
re-fetch the real objects inside the worker:

.. code:: python

    # tasks.py
    from celery import shared_task
    from django.contrib.contenttypes.models import ContentType

    def celery_executor(hook, context):
        payload = context["hook"]["payload"]
        run_hook_via_celery.delay(
            hook._meta.app_label, hook._meta.model_name, hook.pk,
            ContentType.objects.get_for_model(payload["workflow_object"]).pk,
            payload["workflow_object"].pk,
            payload["transition_approval"].pk if "transition_approval" in payload else None,
            context["hook"]["type"], context["hook"]["when"],
        )

    @shared_task
    def run_hook_via_celery(app_label, model_name, hook_pk, ct_id, object_pk, transition_approval_pk, hook_type, when):
        from django.apps import apps
        from django.contrib.contenttypes.models import ContentType
        from xii.django_river.models import Workflow, TransitionApproval

        hook = apps.get_model(app_label, model_name).objects.get(pk=hook_pk)
        workflow_object = ContentType.objects.get(pk=ct_id).get_object_for_this_type(pk=object_pk)
        context = {
            "hook": {
                "type": hook_type, "when": when,
                "payload": {
                    "workflow": Workflow.objects.get(content_type_id=ct_id, field_name=hook.workflow.field_name),
                    "workflow_object": workflow_object,
                    "transition_approval": TransitionApproval.objects.get(pk=transition_approval_pk) if transition_approval_pk else None,
                },
            },
        }
        hook.execute_now(context)

.. code:: python

    # settings.py
    RIVER_HOOK_EXECUTOR = "myproject.tasks.celery_executor"

Whichever executor you use, one trade-off is unavoidable, not a bug: once a
hook runs off-thread or out-of-process, ``RIVER_STRICT_HOOKS``'s guarantee
of propagating an exception to fail the transition no longer applies — the
transition has already committed and returned to the caller by the time an
async hook could fail. Async executors must surface failures through their
own channel (logging, a dead-letter queue, monitoring), not by raising back
into the original request.
