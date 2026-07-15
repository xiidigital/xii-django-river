.. _migration_river_to_xii_django_river:

``river`` to ``xii.django_river`` (required reading before upgrading)
=======================================================================

.. note::
    This guide is specific to this fork (``xii-django-river``). It applies
    to **anyone who already has this fork installed with the Python package
    imported as ``river`` and the Django ``app_label`` set to ``river``**
    (i.e. ``INSTALLED_APPS`` contained ``'river'``, tables are named
    ``river_workflow``, ``river_function``, etc., and permissions look like
    ``river.add_workflow``).

Starting with this release, the importable package moved from ``river`` to
``xii.django_river`` (a nested package: top-level ``xii`` containing a
``django_river`` subpackage), and the Django ``app_label`` changed from
``river`` to ``xii_django_river``. ``INSTALLED_APPS`` now has to list
``'xii.django_river'`` instead of ``'river'``.

This is a **confirmed, deliberate breaking change**. Renaming a Django
``app_label`` is not something Django supports out of the box — there is no
built-in migration operation for it — so upgrading requires a manual,
one-time data-and-schema fix-up on any database that was already migrated
under the old ``river`` app_label. If you are installing this fork fresh
(no existing ``river_*`` tables), none of this applies to you: just install
normally and use ``'xii.django_river'`` in ``INSTALLED_APPS`` from the
start.

What changes, concretely
-------------------------

* **Table names** — every table Django created for this app is prefixed
  with the app_label, so ``river_workflow``, ``river_state``,
  ``river_transition``, ``river_transitionmeta``, ``river_transitionapproval``,
  ``river_transitionapprovalmeta``, ``river_function``,
  ``river_functionrevision``, ``river_onapprovedhook``,
  ``river_ontransithook``, ``river_oncompletehook`` (check your database for
  the exact list — it depends on which models/migrations you have applied)
  all become ``xii_django_river_<model>``.
* **Content types** — ``django_content_type`` rows for these models have
  ``app_label = 'river'``; they need to become
  ``app_label = 'xii_django_river'``.
* **Permissions** — ``auth_permission`` rows are keyed off ``content_type``,
  so they follow automatically once content types are fixed (no separate
  SQL needed for the permission table itself). However, any permission
  strings **hardcoded in your own application code** (for example
  ``request.user.has_perm('river.add_workflow')`` or
  ``river.approve_function`` / ``river.self_approve_function``) must be
  updated to the ``xii_django_river.*`` equivalents.
* **Migration history** — ``django_migrations`` rows for this app have
  ``app = 'river'`` across several migration names (``0001_initial`` through
  ``0006_...`` in older versions of this fork); they need to become
  ``app = 'xii_django_river'`` so Django considers them already applied
  under the new label and doesn't try to re-run them against tables that
  already exist. As of this release, this fork's own migrations have been
  **squashed into a single** ``0001_initial`` (there is no real deployment
  history to preserve yet, and the manual table-rename path below doesn't
  depend on Django's migration graph anyway). A row named ``0001_initial``
  in your rewritten history will be treated as already applied; any leftover
  rows named ``0002_...`` through ``0006_...`` are harmless — Django ignores
  applied-migration rows that no longer correspond to a file — but you can
  delete them for tidiness (see step 4).

Step-by-step
------------

1. **Do not deploy the new ``INSTALLED_APPS`` value yet.** Run the SQL
   fix-up below first, against your production database (or run it as part
   of the same deploy, before Django starts serving traffic with the new
   settings).

2. Rename each ``river_<model>`` table to ``xii_django_river_<model>``. The
   syntax differs per database engine:

   PostgreSQL:

   .. code:: sql

       ALTER TABLE river_workflow RENAME TO xii_django_river_workflow;
       ALTER TABLE river_state RENAME TO xii_django_river_state;
       ALTER TABLE river_transition RENAME TO xii_django_river_transition;
       ALTER TABLE river_transitionmeta RENAME TO xii_django_river_transitionmeta;
       ALTER TABLE river_transitionapproval RENAME TO xii_django_river_transitionapproval;
       ALTER TABLE river_transitionapprovalmeta RENAME TO xii_django_river_transitionapprovalmeta;
       ALTER TABLE river_function RENAME TO xii_django_river_function;
       ALTER TABLE river_functionrevision RENAME TO xii_django_river_functionrevision;
       ALTER TABLE river_onapprovedhook RENAME TO xii_django_river_onapprovedhook;
       ALTER TABLE river_ontransithook RENAME TO xii_django_river_ontransithook;
       ALTER TABLE river_oncompletehook RENAME TO xii_django_river_oncompletehook;
       -- ...and any many-to-many "through" tables (e.g.
       -- river_transitionapprovalmeta_permissions,
       -- river_transitionapprovalmeta_groups,
       -- river_transitionapproval_permissions,
       -- river_transitionapproval_groups) if they exist in your schema.

   MySQL:

   .. code:: sql

       RENAME TABLE river_workflow TO xii_django_river_workflow;
       RENAME TABLE river_state TO xii_django_river_state;
       -- ... one RENAME TABLE per table, same list as above.

   Microsoft SQL Server:

   .. code:: sql

       EXEC sp_rename 'river_workflow', 'xii_django_river_workflow';
       EXEC sp_rename 'river_state', 'xii_django_river_state';
       -- ... one sp_rename per table, same list as above.

   .. warning::
       Confirm the exact table list against your own database
       (``\dt river_*`` on PostgreSQL, ``SHOW TABLES LIKE 'river_%'`` on
       MySQL, or querying ``sys.tables`` on MSSQL) before running these
       statements — the list above is derived from the models as of this
       release and may not match an older or newer schema you're running.

3. Update ``django_content_type``:

   .. code:: sql

       UPDATE django_content_type SET app_label = 'xii_django_river' WHERE app_label = 'river';

4. Update ``django_migrations`` so Django treats the existing migration
   history as already applied under the new label:

   .. code:: sql

       UPDATE django_migrations SET app = 'xii_django_river' WHERE app = 'river';

   Optionally, since this fork's migrations are now squashed to a single
   ``0001_initial``, you can also delete the now-superseded rows so
   ``showmigrations`` reflects the current file layout exactly:

   .. code:: sql

       DELETE FROM django_migrations
       WHERE app = 'xii_django_river' AND name <> '0001_initial';

   This step is cosmetic only — leaving the old rows in place does not
   break anything.

5. Update ``INSTALLED_APPS`` in your settings from ``'river'`` to
   ``'xii.django_river'``, and update every import in your own codebase
   from ``river.*`` to ``xii.django_river.*`` (e.g.
   ``from river.models.fields.state import StateField`` becomes
   ``from xii.django_river.models.fields.state import StateField``).

6. Update any hardcoded permission strings in your own code —
   ``'river.add_workflow'``, ``'river.approve_function'``,
   ``'river.self_approve_function'``, and similarly for any other
   ``river.<perm>`` permission you check — to ``'xii_django_river.<perm>'``.

7. Check for engine-specific objects that embed the old table name in their
   own identifier — foreign key constraint names, index names, or sequence
   names on PostgreSQL (e.g. ``river_workflow_id_seq``), auto_increment
   metadata on MySQL, or named constraints on MSSQL. Renaming the table
   itself is enough for Django and for querying data; only rename these if
   your own tooling (monitoring, other raw SQL, DBA conventions) depends on
   the constraint/index name matching the table name.

8. Deploy the application with the updated ``INSTALLED_APPS`` and imports.
   Run ``python manage.py migrate`` — it should report "No migrations to
   apply" for ``xii_django_river``, confirming Django sees the renamed
   tables and the rewritten migration history as consistent.

Verifying the migration worked
-------------------------------

* ``python manage.py showmigrations xii_django_river`` should show
  ``0001_initial`` as applied (``[X]``), with no new migrations pending.
  (If you skipped the optional cleanup in step 4, you may still see
  ``0002_...`` through ``0006_...`` listed as applied — that's expected and
  harmless, they're just no longer represented by files.)
* ``python manage.py check`` should report no issues.
* Spot-check a permission: ``Permission.objects.filter(content_type__app_label='xii_django_river')``
  should return the full set that used to be under ``app_label='river'``.
* If you have a staging environment with a copy of production data, run
  this whole procedure there first.
