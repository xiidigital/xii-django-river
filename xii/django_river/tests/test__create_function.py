from django.test import TestCase
from hamcrest import assert_that, equal_to, is_not

from xii.django_river.models.function import Function, create_function


class CreateFunctionTest(TestCase):
    """
    Regression test: create_function(callback) used to look up an existing
    Function row by (name, body) together via get_or_create(name=..., body=...).
    Since `name` is unique, re-registering a callback whose source body had
    changed (a normal code edit) but whose name stayed the same found no row
    matching both fields, then tried to create() a second row with the same
    `name` and crashed with IntegrityError - breaking the exact "the code
    changed, re-register it" use case this helper exists for.
    """

    def test_reRegisteringWithUnchangedBodyIsIdempotent(self):
        def _stable_callback(context):
            context["touched"] = True

        first = create_function(_stable_callback)
        second = create_function(_stable_callback)

        assert_that(first.pk, equal_to(second.pk))
        assert_that(second.version, equal_to(first.version))
        assert_that(Function.objects.filter(name=first.name).count(), equal_to(1))

    def test_reRegisteringWithAChangedBodyUpdatesInPlaceInsteadOfCrashing(self):
        def _versioned_callback(context):
            context["version"] = 1

        first = create_function(_versioned_callback)
        first_version = first.version

        def _versioned_callback(context):  # noqa: F811 - deliberately redefined, same name
            context["version"] = 2

        second = create_function(_versioned_callback)

        assert_that(second.pk, equal_to(first.pk))
        assert_that(second.version, is_not(equal_to(first_version)))
        assert_that(second.is_approved, equal_to(True))
        assert_that(Function.objects.filter(name=first.name).count(), equal_to(1))

        context = {}
        second.get()(context)
        assert_that(context.get("version"), equal_to(2))
