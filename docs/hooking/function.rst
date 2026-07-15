.. _hooking_function_guide:

.. |Create Function Page| image:: /_static/create-function.png

Functions
=========

Functions are the description in ``Python`` of what you want to do on certain events happen. So you define them once and you can use them
with multiple hooking up. Just go to ``/admin/xii_django_river/function/`` admin page and create your functions there.``xii-django-river`` function admin support
python code highlighting as well if you enable the ``codemirror2`` app. Don't forget to collect statics for production deployments.


   .. code:: python

       INSTALLED_APPS=[
           ...
           codemirror2
           xii.django_river
           ...
       ]

Here is an example function;

   .. code:: python

        from datetime import datetime

        def handle(context):
            print(datetime.now())

**Important:** **YOUR FUNCTION SHOULD BE NAMED AS** ``handle``. Otherwise ``xii-django-river`` won't execute your function.

|Create Function Page|

.. _hooking_function_security_gates:

Before it runs: three gates (fork-specific)
--------------------------------------------

``Function.body`` is stored as text and executed with ``exec()`` (or, with
the sandbox described below, with ``RestrictedPython``). That means
**anyone who can write to the Function table can run arbitrary Python in
your application's process.** This fork adds three independent gates in
front of that, all off/strict by default so nothing runs by accident:

1. ``RIVER_ALLOW_DB_FUNCTIONS`` (setting, default ``False``) — a
   deployment-wide switch. ``Function.get()`` refuses to execute anything
   at all unless this is explicitly set to ``True``. It exists so that
   using DB-stored hooks is a conscious choice by whoever configures the
   project, not a silent default.
2. ``Function.is_approved`` (model field, default ``False``) — a
   per-``Function`` review gate, independent of the setting above. Editing
   a ``Function``'s ``body`` resets ``is_approved`` to ``False``: a
   reviewer has to sign off on the *new* code, not the old one.
3. ``Hook.save()`` validation — attaching a ``Hook`` to a ``Function`` that
   isn't approved raises ``ValidationError`` immediately, whether you're
   using the admin, a data migration, or plain ORM code. A misconfigured
   hook is rejected when you configure it, not discovered later at
   runtime.

.. code:: python

    # settings.py
    RIVER_ALLOW_DB_FUNCTIONS = True  # opt in explicitly

Approving a ``Function``
^^^^^^^^^^^^^^^^^^^^^^^^^

Two Django permissions control who can move a ``Function`` from
"pending" to "approved":

* ``xii_django_river.approve_function`` — required to use the "Approve selected
  functions" action on the ``Function`` admin page at all.
* ``xii_django_river.self_approve_function`` — required, *in addition to the above*,
  for the same person who last edited a ``Function`` to approve their own
  change. Without it, approving your own edit raises
  ``ImproperlyConfigured``.

Which of these to grant, and to whom, depends on who is trusted to author
hooks in your deployment — see :ref:`security_guide` for a full
discussion of the trade-offs (single trusted team vs. a platform operator
reviewing tenant-authored hooks vs. fully autonomous tenants with no
external reviewer at all).

Programmatic approval is available through the model API too:

.. code:: python

    function.approve(reviewer_user)
    # or, when the author is explicitly allowed to sign off on their own work:
    function.approve(author_user, allow_self_approval=True)

Every creation, edit, and approval of a ``Function`` is written to an
immutable ``FunctionRevision`` row — a diff against the previous body,
who changed it, when, and (for approvals) whether it was a normal approval
or a self-approval. This is visible as a read-only inline on the
``Function`` admin page; nobody, including superusers, can edit or delete
past revisions from the UI.

Functions registered from code
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``xii.django_river.models.function.create_function(callback)`` registers a plain
Python function *defined in your codebase* as a ``Function`` row (this is
how you satisfy ``Hook.callback_function``'s mandatory foreign key without
hand-typing code into the admin). Since that body already went through
your normal code review process (a pull request, CI, etc.), there's
nothing left for a ``Function``-level reviewer to sign off on — rows
created this way are approved automatically.

Optional sandbox: ``RIVER_SANDBOX_DB_FUNCTIONS``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, an approved ``Function`` still runs with plain ``exec()`` —
full access to whatever the Python process can reach. Setting
``RIVER_SANDBOX_DB_FUNCTIONS = True`` (requires
``pip install xii-django-river[sandbox]``) compiles the body through
`RestrictedPython <https://restrictedpython.readthedocs.io/>`_ instead:

* ``import`` statements don't resolve (no ``__import__`` in the restricted
  builtins) — they fail with an error the moment ``handle`` actually tries
  to import something.
* Dunder attribute access (the classic
  ``().__class__.__bases__[0].__subclasses__()`` sandbox escape) is
  rejected at *compile* time, before the code can even run.
* ``__builtins__`` is replaced with RestrictedPython's ``safe_builtins``
  — no ``open``, ``eval``, ``exec``, or ``compile`` available to the body.

This is opt-in and **not fully backward compatible**: bodies that rely on
``import`` or on reaching anything outside the ``context`` argument will
need rewriting. It is also not a complete sandbox — see
:ref:`security_guide` for what it does and does not cover (no CPU/memory/
time limits, and objects you choose to expose via ``context`` are still
reachable with their full attribute surface).

Context Parameter
-----------------

``xii-django-river`` will pass a ``context`` down to your function in order for you to know why the function is triggered or for which object or so. And the ``context``
will look different for different type of events. But it also has some common parts for all the events. Let's look at how it looks;


``context.hook ->>``

+---------------------+--------+--------------------+---------------------------------------------------------+
|      Key            |  Type  |       Format       |                       Description                       |
+=====================+========+====================+=========================================================+
| type                | String | | * on-approved    | | The event type that is hooked up. The payload will    |
|                     |        | | * on-transit     | | likely differ according to this value                 |
|                     |        | | * on-complete    |                                                         |
+---------------------+--------+--------------------+---------------------------------------------------------+
| when                | String | | * BEFORE         | | Whether it is hooked right before the event happens   |
|                     |        | | * AFTER          | | or right after                                        |
+---------------------+--------+--------------------+---------------------------------------------------------+
| payload             | dict   |                    | | This is the context content that will differ for each |
|                     |        |                    | | event type. The information that can be gotten from   |
|                     |        |                    | | payload is describe in the table below                |
+---------------------+--------+--------------------+---------------------------------------------------------+

Context Payload
---------------

On-Approved Event Payload
^^^^^^^^^^^^^^^^^^^^^^^^^
+---------------------+------------------+---------------------------------------------------------+
|      Key            |  Type            |                       Description                       |
+=====================+==================+=========================================================+
| workflow            | Workflow Model   | The workflow that the transition currently happening    |
+---------------------+------------------+---------------------------------------------------------+
| workflow_object     | | Your Workflow  | | The workflow object of the model that has the state   |
|                     | | Object         | | field in it                                           |
+---------------------+------------------+---------------------------------------------------------+
| transition_approval | | Transition     | | The approval object that is currently approved which  |
|                     | | Approval       | | contains the information of the transition(meta) as   |
|                     |                  | | well as who approved it etc.                          |
+---------------------+------------------+---------------------------------------------------------+

On-Transit Event Payload
^^^^^^^^^^^^^^^^^^^^^^^^
+---------------------+------------------+---------------------------------------------------------+
|      Key            |  Type            |                       Description                       |
+=====================+==================+=========================================================+
| workflow            | Workflow Model   | The workflow that the transition currently happening    |
+---------------------+------------------+---------------------------------------------------------+
| workflow_object     | | Your Workflow  | | The workflow object of the model that has the state   |
|                     | | Object         | | field in it                                           |
+---------------------+------------------+---------------------------------------------------------+
| transition_approval | | Transition     | | The last transition approval object which contains    |
|                     | | Approval       | | the information of the transition(meta) as well as    |
|                     |                  | | who last approved it etc.                             |
+---------------------+------------------+---------------------------------------------------------+


On-Complete Event Payload
^^^^^^^^^^^^^^^^^^^^^^^^^
+---------------------+------------------+---------------------------------------------------------+
|      Key            |  Type            |                       Description                       |
+=====================+==================+=========================================================+
| workflow            | Workflow Model   | The workflow that the transition currently happening    |
+---------------------+------------------+---------------------------------------------------------+
| workflow_object     | | Your Workflow  | | The workflow object of the model that has the state   |
|                     | | Object         | | field in it                                           |
+---------------------+------------------+---------------------------------------------------------+




Example Function
^^^^^^^^^^^^^^^^

   .. code:: python

        from xii.django_river.models.hook import BEFORE, AFTER

        def _handle_my_transitions(hook):
            workflow = hook['payload']['workflow']
            workflow_object = hook['payload']['workflow_object']
            source_state = hook['payload']['transition_approval'].meta.transition_meta.source_state
            destination_state = hook['payload']['transition_approval'].meta.transition_meta.destination_state
            last_approved_by = hook['payload']['transition_approval'].transactioner
            if hook['when'] == BEFORE:
                print('A transition from %s to %s will soon happen on the object with id:%s and field_name:%s!' % (source_state.label, destination_state.label, workflow_object.pk, workflow.field_name))
            elif hook['when'] == AFTER:
                print('A transition from %s to %s has just happened on the object with id:%s and field_name:%s!' % (source_state.label, destination_state.label, workflow_object.pk, workflow.field_name))
            print('Who approved it lately is %s' % last_approved_by.username)

        def _handle_my_approvals(hook):
            workflow = hook['payload']['workflow']
            workflow_object = hook['payload']['workflow_object']
            approved_by = hook['payload']['transition_approval'].transactioner
            if hook['when'] == BEFORE:
                print('An approval will soon happen by %s on the object with id:%s and field_name:%s!' % ( approved_by.username, workflow_object.pk, workflow.field_name ))
            elif hook['when'] == AFTER:
                print('An approval has just happened by %s  on the object with id:%s and field_name:%s!' % ( approved_by.username, workflow_object.pk, workflow.field_name ))

        def _handle_completions(hook):
            workflow = hook['payload']['workflow']
            workflow_object = hook['payload']['workflow_object']
            if hook['when'] == BEFORE:
                print('The workflow will soon be complete for the object with id:%s and field_name:%s!' % ( workflow_object.pk, workflow.field_name ))
            elif hook['when'] == AFTER:
                print('The workflow has just been complete for the object with id:%s and field_name:%s!' % ( workflow_object.pk, workflow.field_name ))

        def handle(context):
            hook = context['hook']
            if hook['type'] == 'on-transit':
                _handle_my_transitions(hook)
            elif hook['type'] == 'on-approved':
                _handle_my_approvals(hook)
            elif hook['type'] == 'on-complete':
                _handle_completions(hook)
            else:
                print("Unknown event type %s" % hook['type'])
