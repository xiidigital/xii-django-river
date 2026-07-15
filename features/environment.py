from behave import register_type
from django.core import management

# Run this suite via `manage.py behave --settings=settings.for_behave`.
# Django is already set up by the time management commands execute, so
# there's no need (and it would be wrong to force a settings module here,
# overriding whatever --settings the invocation actually used).


def before_scenario(context, scenario):
    management.call_command('flush', interactive=False)


def parse_string_with_whitespace(text):
    return text


def parse_list(text):
    return [better_item.strip() for item in text.split(" or ") for better_item in item.split(" and ")]


# -- REGISTER: User-defined type converter (parse_type).
register_type(ws=parse_string_with_whitespace)
register_type(list=parse_list)
