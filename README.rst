.. |Logo| image:: docs/logo.svg
    :width: 200

.. |Create Function Page| image:: docs/_static/create-function.png

XII Django River
================

|Logo|

``xii-django-river`` is an open source workflow framework for ``Django`` which supports on
the fly changes instead of hard-coding states, transitions and authorization rules.

The main goal of developing this framework is **to be able to modify literally everything
about the workflows on the fly.** This means that all the elements in a workflow like
states, transitions or authorizations rules are editable at any time so that no changes
requires a re-deploying of your application anymore.

About this fork
----------------
``xii-django-river`` is a fork of `django-river <https://github.com/javrasya/django-river>`_
by Ahmet DAL, maintained by `XII Digital <https://github.com/xiidigital/xii-django-river>`_.
It was forked to (1) modernize the library for current Django (``4.2``-``6.0``) and Python
(``3.10``-``3.13``), and (2) add a security hardening layer around ``xii_django_river.Function``, which
stores Python code as text in the database and executes it via ``exec()``. That's a deliberate
design feature of the original project (hooks can be changed without a deploy), but it means
anyone who can write to the ``Function`` table can run arbitrary code in-process. See "Fork
notes" below for the technical detail, and `SECURITY.md`_ for the full threat model.

All credit for the original design and implementation goes to Ahmet DAL and the
`django-river contributors <https://github.com/javrasya/django-river/graphs/contributors>`_ —
see "Contributors" below.

**Playground**: There is a fake jira example repository as a playground of the original
django-river project. https://github.com/javrasya/fakejira

Support the original maintainer
--------------------------------

``xii-django-river`` itself does not accept donations. If you'd like to support the
original ``django-river`` project and its maintainer, Ahmet DAL, consider becoming a
`sponsor`_, `patron`_, or donating over `PayPal`_.

.. _`patron`: https://www.patreon.com/javrasya
.. _`PayPal`: https://paypal.me/ceahmetdal
.. _`sponsor`: https://github.com/sponsors/javrasya

Documentation
-------------

Online documentation for the original upstream project is available at http://django-river.rtfd.org/.
This fork does not yet publish its own hosted docs; see the ``docs/`` directory in this
repository for fork-specific documentation (including :ref:`security_guide`).

Advance Admin
-------------

A very modern admin with some user friendly interfaces that is called `River Admin`_ has been published
by the original django-river project.

.. _`River Admin`: https://riveradminproject.com/

Requirements (this fork)
------------------------
* Python (``3.10``, ``3.11``, ``3.12``, ``3.13``)
* Django (``4.2``, ``5.0``, ``5.1``, ``5.2``, ``6.0``)
* ``Django`` >= 6.0 requires ``Python`` >= 3.12

Fork notes
----------
This fork modernizes django-river 3.3.0 for current Django. Highlights:

* ``django-mptt`` dependency removed (it was never actually used as a tree).
* ``django-cte`` >= 3.0; ``django-codemirror2`` is now optional
  (``pip install xii-django-river[codemirror]``).
* SQL Server support runs on ``mssql-django``
  (``pip install xii-django-river[mssql]``) with a fully parametrized query.
* The public signals (``pre_approve``, ``post_approve``, ``pre_transition``,
  ``post_transition``, ``pre_on_complete``, ``post_on_complete``) are now
  actually emitted. ``post_*`` signals fire in reverse nesting order
  (on-complete, transition, approve) and only when no exception occurred.
* New settings:

  - ``RIVER_ALLOW_DB_FUNCTIONS`` (default ``False``): hooks execute Python
    code stored in the ``Function`` model via ``exec``. You must opt in
    explicitly, since anyone with admin access to ``Function`` can run
    arbitrary code.
  - ``RIVER_STRICT_HOOKS`` (default ``False``): when ``True``, exceptions
    raised by hooks propagate instead of being swallowed and logged.
  - ``RIVER_SANDBOX_DB_FUNCTIONS`` (default ``False``): compiles
    ``Function`` bodies through RestrictedPython instead of plain
    ``exec()`` (``pip install xii-django-river[sandbox]``).
* ``xii_django_river.Function`` now supports a review workflow: ``is_approved``,
  the ``xii_django_river.approve_function`` / ``xii_django_river.self_approve_function``
  permissions, and an immutable ``FunctionRevision`` audit trail with
  diffs and a username snapshot (survives account deletion).
  ``Hook.save()`` refuses to attach a ``Hook`` to an unapproved
  ``Function``. See `SECURITY.md`_ for the full threat model and what is
  (and isn't) covered by this fork's mitigations.

.. _`SECURITY.md`: SECURITY.md

Supported (Tested) Databases:
-----------------------------

+------------+--------+---------+
| PostgreSQL | Tested | Support |
+------------+--------+---------+
| 9          |   ✅   |    ✅   |
+------------+--------+---------+
| 10         |   ✅   |    ✅   |
+------------+--------+---------+
| 11         |   ✅   |    ✅   |
+------------+--------+---------+
| 12         |   ✅   |    ✅   |
+------------+--------+---------+

+------------+--------+---------+
| MySQL      | Tested | Support |
+------------+--------+---------+
| 5.6        |   ✅   |    ❌   |
+------------+--------+---------+
| 5.7        |   ✅   |    ❌   |
+------------+--------+---------+
| 8.0        |   ✅   |    ✅   |
+------------+--------+---------+

+------------+--------+---------+
| MSSQL      | Tested | Support |
+------------+--------+---------+
| 19         |   ✅   |    ✅   |
+------------+--------+---------+
| 17         |   ✅   |    ✅   |
+------------+--------+---------+


Usage
-----
1. Install and enable it

   .. code:: bash

       pip install xii-django-river


   .. code:: python

       INSTALLED_APPS=[
           ...
           xii.django_river
           ...
       ]

2. Create your first state machine in your model and migrate your db

    .. code:: python

        from django.db import models
        from xii.django_river.models.fields.state import StateField

        class MyModel(models.Model):
            my_state_field = StateField()

3. Create all your ``states`` on the admin page
4. Create a ``workflow`` with your model ( ``MyModel`` - ``my_state_field`` ) information on the admin page
5. Create your ``transition metadata`` within the workflow created earlier, source and destination states
6. Create your ``transition approval metadata`` within the workflow created earlier and authorization rules along with their priority on the admin page
7. Enjoy your ``xii-django-river`` journey.

    .. code-block:: python

        my_model=MyModel.objects.get(....)

        my_model.river.my_state_field.approve(as_user=transactioner_user)
        my_model.river.my_state_field.approve(as_user=transactioner_user, next_state=State.objects.get(label='re-opened'))

        # and much more. Check the documentation

.. note::
    Whenever a model object is saved, it's state field will be initialized with the
    state is given at step-4 above by ``xii-django-river``.

Hooking Up With The Events
--------------------------

`xii-django-river` provides you to have your custom code run on certain events. And since version v2.1.0 this has also been supported for on the fly changes. You can
create your functions and also the hooks to a certain events by just creating few database items. Let's see what event types that can be hooked a function to;

* An approval is approved
* A transition goes through
* The workflow is complete

For all these event types, you can create a hooking with a given function which is created separately and preliminary than the hookings for all the workflow objects you have
or you will possible have, or for a specific workflow object. You can also hook up before or after the events happen.

1. Create Function
^^^^^^^^^^^^^^^^^^

This will be the description of your functions. So you define them once and you can use them with multiple hooking up. Just go to ``/admin/xii_django_river/function/`` admin page
and create your functions there. ``xii-django-river`` function admin support python code highlights.

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

``xii-django-river`` will pass a ``context`` down to your function in order for you to know why the function is triggered or for which object or so. And the ``context`` will look different for
different type of events. Please see detailed `context documentation`_ to know more on what you would get from context in your functions.

You can find an `advance function example`_ on the link.

|Create Function Page|

.. _`context documentation`: https://django-river.readthedocs.io/en/latest/hooking/function.html#context-parameter
.. _`advance function example`: https://django-river.readthedocs.io/en/latest/hooking/function.html#example-function

2. Hook It Up
^^^^^^^^^^^^^

The hookings in ``xii-django-river`` can be created both specifically for a workflow object or for a whole workflow. ``xii-django-river`` comes with some model objects and admin interfaces which you can use
to create the hooks.

* To create one for whole workflow regardless of what the workflow object is, go to

    * ``/admin/xii_django_river/onapprovedhook/`` to hook up to an approval
    * ``/admin/xii_django_river/ontransithook/`` to hook up to a transition
    * ``/admin/xii_django_river/oncompletehook/`` to hook up to the completion of the workflow

* To create one for a specific workflow object you should use the admin interface for the workflow object itself. One amazing feature of ``xii-django-river`` is now that it creates a default admin interface with the hookings for your workflow model class. If you have already defined one, ``xii-django-river`` enriches your already defined admin with the hooking section. It is default disabled. To enable it just define ``RIVER_INJECT_MODEL_ADMIN`` to be ``True`` in the ``settings.py``.


**Note:** They can programmatically be created as well since they are model objects. If it is needed to be at workflow level, just don't provide the workflow object column. If it is needed
to be for a specific workflow object then provide it.

Here are the list of hook models;

* OnApprovedHook
* OnTransitHook
* OnCompleteHook

Before Reporting A Bug
----------------------

``xii-django-river`` has behavioral tests that are very easy to read and write. One can easily set up one
and see if everything is running as expected. Please look at other examples (that are the files with ``.feature`` postfix)
under ``features`` folder that you can get all the inspiration and create one for yourself before you open an issue
Then refer to your behavioral test to point out what is not function as expected to speed the process up for your own
sake. It is even better to name it with your issue number so we can persist it in the repository.

Migrations
----------

2.X.X to 3.0.0
^^^^^^^^^^^^^^

``django-river`` v3.0.0 (upstream, before this fork existed) comes with quite number of migrations, but the good news is that even though those are hard to determine kind of migrations, it comes with the required migrations
out of the box. All you need to do is to run;


   .. code:: bash

       python manage.py migrate river

3.1.X to 3.2.X
^^^^^^^^^^^^^^

``django-river`` (upstream, before this fork existed) started to support **Microsoft SQL Server 17 and 19** after version 3.2.0 but the previous migrations didn't get along with it. We needed to reset all
the migrations to have fresh start. If you have already migrated to version `3.1.X` all you need to do is to pull your migrations back to the beginning.


   .. code:: bash

       python manage.py migrate --fake river zero
       python manage.py migrate --fake river

``river`` app_label to ``xii_django_river`` (this fork)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Required reading if you already have this fork installed with
``app_label='river'``.** Starting with this release, the importable package
moved from ``river`` to ``xii.django_river`` and the Django ``app_label``
changed from ``river`` to ``xii_django_river``. This is a breaking change:
table names, permission names, and content-type app labels all change for
any database that was previously migrated under the old ``river`` app_label.
There is no built-in Django operation to rename an app_label in place, so a
manual migration is required before upgrading. See
`docs/migration/migration_river_to_xii_django_river.rst`_ for the full,
step-by-step guide.

.. _`docs/migration/migration_river_to_xii_django_river.rst`: docs/migration/migration_river_to_xii_django_river.rst

FAQ
---

Have a look at `FAQ`_ (documentation inherited from the original upstream project; still applicable to this fork).

.. _`FAQ`: https://django-river.readthedocs.io/en/latest/faq.html

Contributors
============

This fork (``xii-django-river``) is maintained by `XII Digital <https://github.com/xiidigital>`_.
The section below credits the contributors to the **original upstream ``django-river``
project**, whose work this fork builds on.

Code Contributors (original django-river project)
---------------------------------------------------

This project exists thanks to all the people who contributed to the original
``django-river`` project :rocket: :heart:

.. image:: https://opencollective.com/django-river/contributors.svg?width=890&button=false
    :target: https://github.com/javrasya/django-river/graphs/contributors

Financial Contributors (original django-river project)
----------------------------------------------------------

Become a financial contributor to the original ``django-river`` project and help
sustain it. Contribute_

Individuals
^^^^^^^^^^^

.. image:: https://opencollective.com/django-river/individuals.svg?width=890
    :target: https://opencollective.com/django-river

Organizations
^^^^^^^^^^^^^

Support the original ``django-river`` project with your organization. Your logo will
show up here with a link to your website. Contribute_

.. image:: https://opencollective.com/django-river/organization/0/avatar.svg
    :target: https://opencollective.com/django-river/organization/0/website

.. _Contribute: https://opencollective.com/django-river

.. _license:

License
=======

This software is licensed under the `New BSD License`. See the ``LICENSE``
file in the top distribution directory for the full license text.
