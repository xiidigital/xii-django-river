# Deuda técnica — xii-django-river, fork de django-river (post-modernización a Django 4.2–6)

Prioridad = (Impacto + Riesgo) × (6 − Esfuerzo). Escala 1–5.

## Priorizado

| # | Ítem | Tipo | I | R | E | Prio |
|---|------|------|---|---|---|------|
| 1 | ✅ **Hecho** — `Hook.execute()` traga todas las excepciones (solo `LOGGER.exception`). Un hook roto falla en silencio y el workflow continúa. | Código | 3 | 4 | ✅ **Hecho** (gate `RIVER_ALLOW_DB_FUNCTIONS`, default `False`) — 1 | 35 |
| 2 | ✅ **Hecho** — Bug de caché en `Function.get()`: lee de `loaded_functions` por `self.name` pero guarda por `self.pk` → nunca hay hit; recompila con `exec()` el cuerpo en **cada** ejecución de hook. | Código | 3 | 3 | 1 | 30 |
| 3 | ✅ **Hecho** (se decidió completar, no eliminar) — Soporte MSSQL legacy: driver con SQL crudo (`sql_server.pyodbc`, paquete muerto; hoy sería `mssql-django`), cursor abierto en `__init__` que nunca se usa ni cierra, `RiverQuerySet.first()` hack, base de manager condicional decidida en import (`app_config.IS_MSSQL` toca `connection`), `settings/with_mssql.py`. Si no usas SQL Server, es complejidad pura. | Arquitectura | 3 | 3 | 2 | 24 |
| 4 | `Function` ejecuta Python arbitrario almacenado en BD (`exec`/`eval`). Es una feature de diseño, pero cualquier usuario con acceso al admin de `Function` tiene RCE. Falta gate (setting `RIVER_ALLOW_DB_FUNCTIONS`, permiso dedicado, o allowlist de módulos). | Seguridad | 2 | 5 | 3 | 21 |
| 5 | ✅ **Hecho** (se emiten desde los context managers) — Señales muertas: `pre_transition`, `post_transition`, `pre_approve`, `post_approve`, `pre_on_complete`, `post_on_complete` se declaran en `signals.py` pero **nunca se emiten** (`.send()` no existe en el código). Quien conecte receivers no recibirá nada. Emitirlas desde los context managers o borrarlas. | Código | 2 | 3 | 2 | 20 |
| 6 | ✅ **Hecho** — `RiverObject.__getattr__` lanza `Exception` genérica en vez de `AttributeError` → rompe `hasattr()`, copy, pickle e introspección sobre modelos con `StateField`. | Código | 2 | 3 | 1 | 25 |
| 7 | ✅ **Hecho** — `WorkflowRegistry` indexa por `id(cls)`: frágil con autoreload del dev server (ids reciclables tras GC) y no soporta herencia. Usar la clase como clave. | Código | 2 | 3 | 2 | 20 |
| 8 | ✅ **Hecho** (system check `xii_django_river.W001`) — `RiverApp.ready()` consulta la BD al arrancar (`RuntimeWarning` en Django 5+). Mover el aviso de "workflow sin definir" a un system check (`@register(Tags.database)`). | Código | 2 | 2 | 1 | 20 |
| 9 | ✅ **Hecho** — Esquema GenericFK: `object_id` es `CharField(50)` en `Transition`/`TransitionApproval` pero `CharField(200)` en hooks, y el driver ORM castea a 200. Sin índice compuesto `(content_type, object_id)` en ninguna tabla → escaneos en cada lookup por objeto. Unificar a 200 + `models.Index`. | Esquema | 2 | 3 | 2 | 20 |
| 10 | ✅ **Hecho** — `RiverConfig` cachea settings para siempre (`cached_settings`) → ignora `override_settings` en tests y cualquier cambio dinámico; `IS_MSSQL` se congela con la conexión default. | Código | 2 | 2 | 2 | 16 |
| 11 | ✅ **Hecho** — Rendimiento del core: `initialize_approvals` y `_re_create_cycled_path` crean filas una a una en bucles (sin `bulk_create`), `approve()` hace `count()` repetidos, `jump_to` guarda approvals uno a uno. Con workflows grandes o creación masiva de objetos, explota en consultas. | Código | 3 | 2 | 3 | 15 |
| 12 | ✅ **Hecho** — Empaquetado/CI: `setup.py` legacy (migrar a `pyproject.toml`), `.travis.yml` (Travis muerto), `tox.ini` apunta a Djangos 1.11–3.x, `publish.sh`, `.idea/` versionado. Sin CI en el fork → regresiones invisibles. Añadir GitHub Actions con matriz py3.10–3.13 × Django 4.2/5.2/6.0. | Infra | 2 | 2 | 2 | 16 |
| 13 | ✅ **Hecho** — Deuda de tests: 7 tests de migraciones skippeados desde Django 2 (borrar), test que escribe migraciones en `xii/django_river/tests/volatile/` en runtime, stack pesado (hamcrest + behave + factory-boy). Los BDD de `features/` no corren en CI. | Tests | 2 | 2 | 3 | 12 |
| 14 | ✅ **Hecho** — Naming/limpieza: typo `wokflow_object_class` en toda la API de drivers, archivos `transitionmetada.py`/`workflowmetada.py`, `Transition.objects = TransitionApprovalManager()` (manager de otra entidad, funciona por accidente), `details()` casi sin uso, try/except de imports pre-Django-1.9 (`GenericForeignKey`). | Código | 2 | 1 | 2 | 12 |
| 15 | ✅ **Hecho** — Docs desactualizadas: `docs/` y `README.rst` mencionan versiones/instrucciones viejas y las señales del punto 5. | Docs | 1 | 2 | 2 | 12 |

## Plan por fases (compatible con trabajo normal)

**Fase 1 — Quick wins (≈½ día):** ✅ completada. #1 (setting `RIVER_STRICT_HOOKS`, default False para compatibilidad), #2, #6, #8, #5 (emitir o borrar señales).

**Fase 2 — Simplificación (≈1 día):** ✅ completada. #7; #10; #14. (El soporte MSSQL se completó en vez de eliminarse: driver parametrizado sobre `mssql-django`, extra `xii-django-river[mssql]`.)

**Fase 3 — Esquema y rendimiento:** ✅ completada. #9 (unificar `object_id` + índices compuestos), #11 (`bulk_create`, menos `count()`).

**Fase 4 — Infra y docs:** ✅ completada. #12, #13, #15, gate de seguridad #4.

## Notas

- `.pypirc` está cifrado con git-crypt (sin exposición de credenciales).
- mptt ya eliminado; django-cte migrado a API 3.x; suite verde (57 tests) en Django 5.2.

## Registro de cambios Fase 1 (2026-07-11)

- `Hook.execute`: nueva setting `RIVER_STRICT_HOOKS` (default `False`); en estricto, las excepciones de hooks se propagan.
- `Function.get()`: caché por `pk` validando `version` y `body`; ya no recompila en cada llamada.
- Señales `pre/post_approve`, `pre/post_transition`, `pre/post_on_complete` ahora se emiten (sender = clase del workflow object; los `post_*` solo si no hubo excepción). Test: `xii/django_river/tests/test__signals.py`.
- `RiverObject.__getattr__` lanza `AttributeError`.
- Aviso de workflow sin definir movido de `ready()` a system check `xii_django_river.W001` (tag `database`); desaparece el `RuntimeWarning` de Django 5+.
- MSSQL completado: driver reescrito con SQL parametrizado (valores como parámetros, identificadores con `quote_name`), sin cursor huérfano, plantilla cacheada, estados comparados por parámetro (antes `'PENDING'` literal, dependía de collation CI); motor `mssql-django` en settings y extra `pip install xii-django-river[mssql]`. Sin SQL Server en CI, la construcción de la consulta se cubre en `xii/django_river/tests/driver/test__mssql_driver.py`.
- Suite: 61 tests OK (7 skips legacy).

## Registro de cambios Fase 2 (2026-07-11)

- `WorkflowRegistry` indexado por clase (no `id(cls)`); nueva propiedad `registered_classes`, `get_class_fields()` tolerante a clases no registradas.
- `RiverConfig` lee settings en cada acceso: `override_settings` y cambios dinámicos funcionan; `IS_MSSQL` se evalúa contra la conexión actual. (Nota: la base de `TransitionApprovalManager` se sigue eligiendo en import.)
- Typo `wokflow_object_class` → `workflow_object_class` en drivers y core.
- `managers/transitionmetada.py` → `managers/transitionapprovalmeta.py`; `managers/workflowmetada.py` → `managers/workflow.py` (git mv, historia preservada).
- Lógica de `workflow_object` extraída a `WorkflowObjectFilteringMixin`; `Transition` usa su propio `TransitionManager` (antes reutilizaba `TransitionApprovalManager` por accidente).
- Imports directos de `GenericForeignKey`/`GenericRelation` (fuera los try/except pre-Django-1.9); `hook.py` ya no importa `GenericForeignKey` vía star-import de `xii.django_river.models`.
- Eliminado `details()` sin uso en `BaseModel` y `State`.
- Suite: 61 tests OK, `makemigrations --check` sin cambios.

## Registro de cambios Fases 3 y 4 (2026-07-11)

### Fase 3 — esquema y rendimiento
- Migración `0003_unify_object_id_and_indexes`: `object_id` unificado a `CharField(200)` en `Transition`/`TransitionApproval` + índices compuestos `(content_type, object_id)` en ambas tablas.
- `initialize_approvals` y `_re_create_cycled_path` con `prefetch_related` de metas/approvals y sus M2M (elimina N+1); `jump_to` con `update()` masivo (aprovaciones y transiciones, con `date_updated`); `approve()`/`on_final_state`/`_check_if_it_cycled`/peers con `exists()` en vez de `count()` repetidos.
- `bulk_create` descartado deliberadamente: MSSQL no garantiza PKs de vuelta en bulk insert y las M2M de approvals necesitan las PKs.

### Fase 4 — seguridad, infra, tests y docs
- Gate `RIVER_ALLOW_DB_FUNCTIONS` (default `False`): `Function.get()` lanza `ImproperlyConfigured` si no se habilita explícitamente. Test: `xii/django_river/tests/test__function_gate.py`. **Breaking change consciente**: quien use hooks debe añadir `RIVER_ALLOW_DB_FUNCTIONS = True`.
- `setup.py`/`setup.cfg` → `pyproject.toml` (wheel verificado: SQL de MSSQL incluido, tests excluidos); `.travis.yml`, `publish.sh` eliminados; `.idea/` fuera del índice de git; `tox.ini` con matriz py3.10–3.13 × Django 4.2/5.2/6.0.
- GitHub Actions: `ci.yml` (matriz + chequeo de migraciones faltantes + tests) y `pythonpublish.yml` modernizado (`python -m build`).
- Eliminados `xii/django_river/tests/tmigrations/` (7 tests skippeados desde Django 2) y `xii/django_river/tests/volatile/`; el chequeo de migraciones faltantes vive ahora en CI (`makemigrations --check`).
- README: requisitos actualizados, sección "Fork notes" (mptt fuera, cte 3.x, extras codemirror/mssql, señales emitidas, settings nuevas); `docs/getting_started.rst` con versiones actuales.

### Estado final
- 54 tests OK, 0 skips. `migrate` desde cero aplica 0001→0003. `makemigrations --check` limpio. `check` sin warnings. Wheel `xii_django_river-4.0.0` construye.
- Pendiente sin resolver en ese momento: nada de la lista original. Ítems de mantenimiento futuro: correr los BDD de `features/` en CI (resuelto, ver registro del 2026-07-15 más abajo) y probar MSSQL contra un servidor real (sigue pendiente).

## Registro de cambios — endurecimiento de `Function` (2026-07-11, sesión posterior)

Ampliación del ítem #4 (gate `RIVER_ALLOW_DB_FUNCTIONS`): ese gate resuelve "¿el sistema permite ejecutar código de BD?" pero no resuelve "¿quién puede autorizar que ESTE código específico corra?". Se agregó:

- `Function.is_approved` + `approve_function`/`self_approve_function` (permisos separados) + `FunctionRevision` (auditoría inmutable con diff, quién, cuándo; acciones `CREATED`/`UPDATED`/`APPROVED`/`SELF_APPROVED`). Migraciones `0004`, `0005`.
- Fix: caché de `Function.get()` (`loaded_functions`) estaba indexada solo por `pk` — bajo multitenancy schema-per-tenant, dos tenants pueden compartir el mismo `pk` y pisarse la caché entre sí (ejecución cruzada de código). Ahora la clave incluye `connection.schema_name`.
- Tests: `xii/django_river/tests/test__function_approval.py` (7 casos). Suite total: 61 tests OK.
- Documentado en `SECURITY.md`: qué mitiga este fork, qué NO mitiga todavía (sandboxing del `exec()`, aislamiento de roles de BD por tenant, límites de recursos), y cómo decidir `RIVER_STRICT_HOOKS` y las políticas de permisos según el modelo de amenaza del proyecto que consume `river` (equipo único de confianza vs. multi-tenant con supervisor vs. multi-tenant con tenants autónomos sin supervisor).
- Pendiente en ese momento, ahora resuelto dentro del fork (ver siguiente registro): validar en el guardado del `Hook`, sandboxing, snapshot de auditoría. Sigue fuera del alcance del fork (depende del proyecto consumidor): roles de BD con privilegio mínimo por tenant.

## Registro de cambios — cierre de items B/C/G (2026-07-11, misma sesión, continuación)

- **B — `Hook.save()` valida aprobación al guardar.** `Hook.clean()`/`Hook.save()` ahora rechazan (`ValidationError`) adjuntar un `Hook` a un `Function` con `is_approved=False`, sin importar el punto de entrada (admin, migración de datos, ORM directo). Antes, un hook mal configurado fallaba en silencio recién al ejecutarse (y solo se veía en logs si `RIVER_STRICT_HOOKS=True`). Esto saca por completo "el Function no está aprobado" de la decisión de `RIVER_STRICT_HOOKS`, que queda como una pregunta puramente de producto: si un bug de runtime en un hook YA aprobado debe tumbar la transición o no. Test: `xii/django_river/tests/test__hook_approval_gate.py`.
- **G — Snapshot de auditoría (`FunctionRevision.changed_by_username`).** Nuevo campo de texto plano poblado en el momento de escribir cada `FunctionRevision`, además del FK `changed_by` (que sigue siendo `SET_NULL`). Si se borra la cuenta, el historial de revisiones sigue diciendo quién hizo qué; solo los campos en vivo de `Function` (`created_by`/`updated_by`/`approved_by`) quedan en `NULL` (documentado como limitación conocida en `SECURITY.md`, ya no crítica porque el historial de auditoría no depende de ellos). Migración `0006`.
- **C — Sandboxing opt-in con RestrictedPython (`xii/django_river/sandbox.py`).** Nuevo setting `RIVER_SANDBOX_DB_FUNCTIONS` (default `False`, no rompe nada existente). Activado, `Function._load()` compila el body con `RestrictedPython.compile_restricted` en vez de `exec()` plano: sin `import` (no hay `__import__` en los builtins restringidos), sin escape vía atributos dunder (rechazado en tiempo de compilación, antes de que el código llegue a correr), `__builtins__` reemplazado por `safe_builtins`. Es opt-in y no 100% retrocompatible — bodies que usan `import` o dependen de alcanzar algo fuera de `context` necesitan reescribirse. No es sandbox completo: no limita CPU/memoria/tiempo, y cualquier objeto ORM/conexión que se pase dentro de `context` sigue siendo alcanzable con su superficie completa. Extra `pip install xii-django-river[sandbox]` (`RestrictedPython>=6.0`); agregado también a `tox.ini` y `.github/workflows/ci.yml` para que la suite de sandbox corra de verdad en CI. Tests: `xii/django_river/tests/test__function_sandbox.py` (bloqueo de `import`, bloqueo de escape por dunder, comportamiento off-by-default).
- `SECURITY.md` actualizado con los tres puntos anteriores movidos de "qué NO hace este fork" a "qué ya hace", y el modelo de amenaza de tenants autónomos ajustado para reflejar que el sandboxing ya es una opción real, no solo teórica.
- Suite total: 69 tests OK (61 + 2 de `test__hook_approval_gate` + 5 de `test__function_sandbox`, más 1 test adicional de snapshot en `test__function_approval`).
- Sigue pendiente, fuera del alcance de este fork: roles de BD con privilegio mínimo por tenant (es infraestructura del proyecto consumidor, no algo que `xii-django-river` pueda resolver desde el ORM). Documentado con guía concreta y genérica (rol Postgres por tenant + `SET LOCAL ROLE` por request/transacción, no una conexión física separada por tenant) en la sección "DB role isolation per tenant" de `SECURITY.md`, incluyendo los caveats reales (pooling, tareas async, `ALTER DEFAULT PRIVILEGES`).

## Registro de cambios — squash de migraciones tras el rename a `xii_django_river` (2026-07-15)

- Las 6 migraciones heredadas (`0001_initial` … `0006_functionrevision_changed_by_username`) se colapsaron en una sola `0001_initial` bajo `xii/django_river/migrations/`. No había ningún despliegue real con historial que preservar bajo `app_label='xii_django_river'` (el label es nuevo de esta misma sesión), y ninguna de las migraciones removidas era una data migration (`RunPython`/`RunSQL`) — todas eran cambios de esquema puros (`AlterField`, `AddField`, `AlterModelOptions`, índices), así que regenerar desde los modelos actuales con `makemigrations` es equivalente al resultado acumulado de las 6 originales.
- Verificado: `manage.py check` sin issues; `migrate` contra una sqlite nueva aplica `0001_initial` en un solo paso (antes 6); suite completa `manage.py test xii.django_river` — 69 tests OK, sin cambios.
- Quien ya tenga este fork instalado bajo el `app_label` viejo (`river`) sigue una única migración manual (ver `docs/migration/migration_river_to_xii_django_river.rst`, que ya cubría ese caso); esa guía se actualizó para reflejar que el destino ahora es un `0001_initial` único, con un paso opcional para limpiar filas huérfanas (`0002`…`0006`) de `django_migrations`.
- Los archivos originales quedan respaldados fuera del repo (no versionados) por si hiciera falta consultarlos; no se conservó ningún registro de ellos dentro del árbol del proyecto porque no aportan valor una vez squasheados.

## Registro de cambios — CI roto post-rename, BDD conectado a CI, secretos/config obsoletos (2026-07-15)

- **CI estaba roto desde el commit del rename.** `.github/workflows/ci.yml` seguía llamando `python manage.py makemigrations river --check` y `python manage.py test river` (label/import viejo); cualquier push desde ese commit habría fallado. Corregido a `xii_django_river` / `xii.django_river`.
- El paso de "chequeo de migraciones faltantes" además crasheaba de forma independiente al rename: usaba `settings.with_sqlite3`, que desactiva `MIGRATION_MODULES` para *todas* las apps, y `makemigrations --check --dry-run` no tolera eso (intenta escribir el archivo de todos modos y explota con `ValueError`). Se agregó `settings/for_migrations_check.py` (idéntico a `with_sqlite3` pero sin desactivar migraciones) para este paso puntual.
- **Suite BDD (`features/`) conectada a CI por primera vez.** Estaba completamente inejecutable: `behave_django` nunca estuvo en `INSTALLED_APPS` (por lo que `manage.py behave` ni existía como comando) y `environment.py` intentaba `django.setup()` manualmente demasiado tarde para `python -m behave` directo. Se agregó `settings/for_behave.py` (extiende `with_sqlite3` + `behave_django`), se limpió `environment.py` (ya no fuerza `DJANGO_SETTINGS_MODULE` ni llama `django.setup()` — innecesario y potencialmente conflictivo bajo `manage.py behave`, que ya inicializa Django antes de correr el comando), y se agregó el job `bdd` en `ci.yml` (`manage.py behave --no-input --settings=settings.for_behave`). Verificado: 4 features, 25 scenarios, 744 steps, todos OK.
- Se eliminaron dos *steps* de Behave sin uso (`a permission with name...`, autorización `with permission`) — ningún `.feature` los invocaba.
- **`.coveralls.yml` eliminado.** Contenía un `repo_token` en texto plano, sin cifrar con git-crypt (a diferencia de `.pypirc`), y no lo usa nada (ni CI ni `tox.ini` referencian Coveralls). Nota: sigue en el historial de git; si el token todavía es válido, conviene revocarlo/rotarlo en coveralls.io.
- `.coveragerc` tenía las mismas rutas viejas que ya se habían corregido en `.codacy.yml` (`river/admin/*`, etc.) — se había pasado por alto porque el archivo no tiene extensión estándar. Corregido a `xii/django_river/*`.
- Se eliminaron dos directorios locales sin uso y con nombres viejos (`xii/django_river/tests/tmigrations/`, `xii/django_river/tests/volatile/river*`), no rastreados por git ni referenciados en ningún lado.

## Registro de cambios — bug real (engine de Postgres) + 4 features nuevas (2026-07-15, misma sesión, continuación)

- **Bug real encontrado en la pasada de auditoría:** `settings/with_postgresql.py` usaba `django.db.backends.postgresql_psycopg2`, alias que Django eliminó hace años (confirmado: `ModuleNotFoundError` en Django 5.2, y lo mismo aplica a cualquier versión 4.2–6.0). Corregido a `django.db.backends.postgresql`. Además: dos imports muertos reales detectados con `pyflakes` (`import django` en `settings/base.py`, `TransitionApprovalMeta` sin usar en `core/classworkflowobject.py`), y `RestrictedPython` faltante en `requirements.txt` (los tests de sandbox fallaban duro, no se saltaban, corriendo la suite local sin ese extra).
- **A — Timeout de ejecución para `Function` (`RIVER_FUNCTION_TIMEOUT_SECONDS`, default `None`).** Nuevo módulo `xii/django_river/timeout.py`: `enforce_timeout()` envuelve la llamada con `signal.alarm`, no-op si el setting no está definido. Integrado dentro de `Function.get()` (no en `Hook.execute_now`), para que aplique a cualquier invocador, no solo a hooks. Limitación real y documentada: solo funciona en el hilo principal con `SIGALRM` (no Windows, no hilos worker — incluido el propio `thread_pool_executor` de abajo); cuando no se puede aplicar, se loguea un WARNING una sola vez en vez de fallar en silencio. Tests: `xii/django_river/tests/test__function_timeout.py`.
- **B — Ejecución plugable de hooks (`RIVER_HOOK_EXECUTOR`, default `None` = síncrono inline, sin cambios).** `Hook.execute()` ahora despacha a un executor configurado si existe; si no, llama a `Hook.execute_now()` directo (comportamiento idéntico al de antes). Nuevo módulo `xii/django_river/executors.py` con `thread_pool_executor` listo para usar (mismo proceso, sin infraestructura nueva) y el contrato documentado para adaptar Celery/RQ/lo que sea. Trade-off explícito: `RIVER_STRICT_HOOKS` deja de poder propagar excepciones una vez que el hook corre fuera del hilo/proceso original — no hay stack al que propagar. Tests: `xii/django_river/tests/test__hook_executor.py` (mockeando `execute_now` para probar el despacho en sí, no la ejecución sandboxeada de `Function`, que ya cubren otros tests).
- **C — Auditoría a nivel de transición (`TransitionAuditLog`).** Nuevo modelo, append-only, con una fila por evento APPROVED/CANCELLED/JUMPED (quién, cuándo — el actor es opcional en JUMPED). A diferencia de `TransitionApproval` (que se muta in-place), esto nunca se actualiza ni borra desde código de aplicación. `InstanceWorkflowObject.jump_to()` ganó un parámetro opcional `as_user=None` (compatible con todos los llamadores existentes) para poder atribuir el salto. Admin de solo lectura (`admin/transition_audit_log.py`), migración `0002_transitionauditlog`. Tests: `xii/django_river/tests/test__transition_audit_log.py`.
- **D — Lint de configuración de workflows (`check_workflow_configuration`, `xii_django_river.W002`/`W003`/`W004`).** Nuevo system check junto al ya existente `check_workflow_definitions` (W001) en `apps.py`. Detecta: transiciones sin ninguna regla de autorización (W002), reglas explícitas sin permisos ni grupos (W003) — ambos casos son, según el código real de `OrmDriver._authorized_approvals`, aprobables por cualquier usuario autenticado, no solo una sospecha — y estados huérfanos que no son origen/destino de ninguna transición ni `initial_state` de ningún workflow (W004). Tests: `xii/django_river/tests/test__workflow_configuration_check.py`.
- Documentado en `README.rst` (Fork notes), `SECURITY.md`/`docs/security.rst` (movido de "qué NO hace" a "qué ya hace" con las salvedades honestas), `docs/changelog.rst`, `docs/hooking/hooking.rst` (ejemplo completo de adaptador a Celery) y `docs/overview.rst` (requisitos desactualizados corregidos de paso: decía Python 2.7–3.6/Django 1.11–3.1, debía decir lo mismo que el README).
- Verificado de punta a punta: `manage.py check` sin issues, suite completa `manage.py test xii.django_river` — 83 tests OK (69 + 14 nuevos), suite BDD sin cambios (744 steps OK), `makemigrations --check` limpio, wheel construye, `pyflakes` limpio en los archivos nuevos y en los tocados.

## Registro de cambios — pasada de optimización/simplificación #2 y bug real en el admin de `Workflow` (2026-07-15, misma sesión, continuación)

- **`_log_audit()` (`core/instanceworkflowobject.py`) pasado a `bulk_create`.** Escribía una fila de `TransitionAuditLog` a la vez dentro de bucles en `cancel_impossible_future()` y `jump_to()` (cada uno puede tocar varias transiciones en una sola llamada); ahora arma la lista de entradas y hace un único `bulk_create()`. `TransitionAuditLog` no tiene M2M ni depende de señales de `save()` por instancia, así que no hay nada que `bulk_create` se salte aquí. Sin cambio de comportamiento observable; verificado con la suite de `test__transition_audit_log.py` (4/4 OK).
- **Bug real encontrado y corregido: `WorkflowAdmin.field_name()` (`admin/workflow.py`) reventaba con `AttributeError` en cada render del changelist de `Workflow`.** El método hacía `return obj.workflow.field_name`, pero `obj` es la instancia de `Workflow` en sí — no tiene atributo `.workflow`. `Workflow` ya tiene su propio campo real `field_name`; el método sobraba y lo único que hacía era taparlo (Django resuelve `list_display` primero contra métodos del `ModelAdmin`, así que el método ganaba sobre el campo del modelo). Nada en la suite ejercitaba esta página de admin, por lo que pasó inadvertido. Corregido eliminando el método; se agregó `xii/django_river/tests/test__workflow_admin.py`, que renderiza el changelist real vía `self.client.get(...)` con un superusuario logueado, para que esta clase de bug no pueda volver a pasar en silencio.
- **`list_select_related` agregado donde faltaba (riesgo de N+1 en listados con FKs sin resolver):** `admin/workflow.py` (`content_type`, `initial_state`), `admin/function_admin.py` (`updated_by`, `approved_by`), `admin/hook_admins.py` (las tres clases: `OnApprovedHookAdmin`, `OnTransitHookAdmin`, `OnCompleteHookAdmin`), `admin/transitionapprovalmeta.py` (`workflow`, `transition_meta`), `admin/transitionmeta.py` (`workflow`, `source_state`, `destination_state`), `admin/transition_audit_log.py` (`workflow`, `source_state`, `destination_state`, `content_type`). Ningún cambio de comportamiento, solo menos queries por página de changelist.
- Revisadas y descartadas deliberadamente dos optimizaciones candidatas: cachear `RiverConfig._defaults()` (rompería `override_settings()` en tests, ya documentado como diseño intencional) y cachear el closure `_timed_call` de `Function.get()` (el overhead de crearlo es insignificante y cachearlo introduciría riesgo de bugs sutiles de binding con `self.name` entre hits de caché).
- Verificado de punta a punta: `manage.py check` sin issues, suite completa `manage.py test xii.django_river` — 84 tests OK (83 + 1 nuevo de `test__workflow_admin`), suite BDD sin cambios (744 steps OK), `makemigrations --check` limpio, wheel construye, Sphinx build limpio con `-W`.
