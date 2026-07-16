from django.contrib import admin
from django.test import TestCase
from hamcrest import assert_that, is_not, has_item, instance_of, equal_to

from xii.django_river.admin import OnApprovedHookInline, OnTransitHookInline, OnCompleteHookInline, DefaultWorkflowModelAdmin
from xii.django_river.models import Function
from xii.django_river.tests.admin import BasicTestModelAdmin
from xii.django_river.tests.models import BasicTestModel, BasicTestModelWithoutAdmin


class AppTest(TestCase):

    def test__shouldInjectExistingAdminOfTheModelThatHasStateFieldInIt(self):
        assert_that(admin.site._registry[BasicTestModel], instance_of(BasicTestModelAdmin))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnApprovedHookInline))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnTransitHookInline))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnCompleteHookInline))

    def test__injectedInlinesAndReadonlyFieldsKeepAStableOrderAcrossRuns(self):
        # Regression test: RiverApp._register_hook_inlines used to dedupe
        # `inlines`/`readonly_fields` with list(set(...)), whose order
        # depends on Python's per-process hash randomization - the admin's
        # column/inline order could silently differ between process
        # restarts. Now deduped with dict.fromkeys(...), which preserves
        # insertion order: the three hook inlines always land at the end,
        # in the same order they're appended in _register_hook_inlines.
        inlines = list(admin.site._registry[BasicTestModel].inlines)
        assert_that(inlines[-3:], equal_to([OnApprovedHookInline, OnTransitHookInline, OnCompleteHookInline]))

    def test__shouldInjectADefaultAdminWithTheHooks(self):
        assert_that(admin.site._registry[BasicTestModelWithoutAdmin], instance_of(DefaultWorkflowModelAdmin))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnApprovedHookInline))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnTransitHookInline))
        assert_that(admin.site._registry[BasicTestModel].inlines, has_item(OnCompleteHookInline))

    def test__shouldNotInjectToAdminOfTheModelThatDoesNotHaveStateFieldInIt(self):
        assert_that(admin.site._registry[Function].inlines, is_not(has_item(OnApprovedHookInline)))
        assert_that(admin.site._registry[Function].inlines, is_not(has_item(OnTransitHookInline)))
        assert_that(admin.site._registry[Function].inlines, is_not(has_item(OnCompleteHookInline)))
