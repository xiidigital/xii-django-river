import os
from os.path import dirname

from django.contrib import auth
from django.contrib.auth.models import Permission
from django.db import connection
from django.db.models import Q

from xii.django_river.driver.river_driver import RiverDriver
from xii.django_river.models import TransitionApproval, PENDING


def _load_sql_template():
    with open(os.path.join(dirname(dirname(__file__)), "sql", "mssql", "get_available_approvals.sql")) as f:
        return f.read()


class MsSqlDriver(RiverDriver):
    """
    Raw T-SQL implementation of ``get_available_approvals`` for SQL Server
    (requires the ``mssql-django`` backend). Identifiers are quoted with the
    backend's ``quote_name`` and every value travels as a query parameter.
    """

    _sql_template = None

    @classmethod
    def _get_sql_template(cls):
        if cls._sql_template is None:
            cls._sql_template = _load_sql_template()
        return cls._sql_template

    def get_available_approvals(self, as_user):
        sql, params = self._build_query(as_user)
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return TransitionApproval.objects.filter(pk__in=[row[0] for row in cursor.fetchall()])

    def _build_query(self, as_user):
        permission_ids = self._permission_ids(as_user)
        group_ids = self._group_ids(as_user)

        quote = connection.ops.quote_name
        opts = self.workflow_object_class._meta
        transitionapproval_meta = TransitionApproval._meta

        sql = self._get_sql_template().format(
            transitionapproval_table=quote(transitionapproval_meta.db_table),
            transition_table=quote(transitionapproval_meta.get_field("transition").related_model._meta.db_table),
            transitionapproval_permissions_table=quote(transitionapproval_meta.get_field("permissions").m2m_db_table()),
            transitionapproval_groups_table=quote(transitionapproval_meta.get_field("groups").m2m_db_table()),
            workflow_object_table=quote(opts.db_table),
            object_pk_column=quote(opts.pk.column),
            state_column=quote(opts.get_field(self.field_name).column),
            permission_placeholders=", ".join(["%s"] * len(permission_ids)),
            group_placeholders=", ".join(["%s"] * len(group_ids)),
        )

        params = [
            self.workflow.pk, PENDING,
            self.workflow.pk, PENDING, as_user.pk,
            *permission_ids,
            *group_ids,
        ]
        return sql, params

    @staticmethod
    def _permission_ids(as_user):
        # Mirrors OrmDriver._authorized_approvals: goes through
        # auth.get_backends() rather than reading user_permissions/group
        # permissions directly, so a user authorized only via a custom auth
        # backend (e.g. an object-level permission backend) is recognized
        # here too, instead of only on non-MSSQL backends.
        permission_strings = set()
        for backend in auth.get_backends():
            permission_strings.update(backend.get_all_permissions(as_user))

        if not permission_strings:
            return [-1]

        permission_q = Q()
        for permission_string in permission_strings:
            label, codename = permission_string.split('.')
            permission_q |= Q(content_type__app_label=label, codename=codename)

        return list(Permission.objects.filter(permission_q).values_list("pk", flat=True)) or [-1]

    @staticmethod
    def _group_ids(as_user):
        return list(as_user.groups.all().values_list("pk", flat=True)) or [-1]
