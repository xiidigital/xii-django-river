from xii.django_river.admin.function_admin import *
from xii.django_river.admin.hook_admins import *
from xii.django_river.admin.transitionapprovalmeta import *
from xii.django_river.admin.transitionmeta import *
from xii.django_river.admin.transition_audit_log import *
from xii.django_river.admin.workflow import *
from xii.django_river.models import State

admin.site.register(State)
