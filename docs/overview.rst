.. |Re Open Case| image:: https://cloud.githubusercontent.com/assets/1279644/9653471/3c9dfcfa-522c-11e5-85cb-f90a4f184201.png

.. |Closed Without Re Open Case| image:: https://cloud.githubusercontent.com/assets/1279644/9624970/88c0ddaa-515a-11e5-8f65-d1e35e945976.png

.. |Closed With Re Open Case| image:: https://cloud.githubusercontent.com/assets/1279644/9624968/88b5f278-515a-11e5-996b-b62d6e224357.png


Overview
========
Main goal of developing this framework is **to be able to edit any workflow item on the fly.** This means, all elements in workflow like states, transitions, user authorizations(permission), group authorization are editable. To do this, all data about the workflow item is persisted into DB. **Hence, they can be changed without touching the code and re-deploying your application.**

There is ordering aprovments for a transition functionality in ``xii-django-river``. It also provides skipping specific transition of a specific objects.

This fork additionally provides: an append-only ``TransitionAuditLog`` of every
approved/cancelled/jumped transition (see :ref:`security_guide`), an opt-in
wall-clock timeout and a pluggable async executor for DB-stored hook
functions (see :ref:`hooking_guide`), and a ``manage.py check`` addition
that flags misconfigured authorization rules and orphaned states.

**Playground**: There is a fake jira example repository as a playground of the original upstream django-river project. https://github.com/javrasya/fakejira

Requirements (this fork)
------------------------
* Python (``3.10``, ``3.11``, ``3.12``, ``3.13``)
* Django (``4.2``, ``5.0``, ``5.1``, ``5.2``, ``6.0``)
* ``Django`` >= 6.0 requires ``Python`` >= 3.12


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

Example Scenarios
-----------------
Simple Issue Tracking System
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Re-Open case
""""""""""""
|Re Open Case|

Closed without Re-Open case
"""""""""""""""""""""""""""
|Closed Without Re Open Case|

Closed with Re-Open case
""""""""""""""""""""""""
|Closed With Re Open Case|