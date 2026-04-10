import pytest

from firetower.incidents.models import Tag, TagType
from firetower.incidents.utils import sort_tags_with_overrides, tag_id_to_group_map


@pytest.mark.django_db
class TestSortTagsWithOverrides:
    def test_empty_groups_preserves_input_order(self):
        t_a = Tag.objects.create(name="a", type=TagType.AFFECTED_REGION)
        t_b = Tag.objects.create(name="b", type=TagType.AFFECTED_REGION)
        ordered = sort_tags_with_overrides([t_b, t_a], [])
        assert [t.name for t in ordered] == ["b", "a"]

    def test_single_group_orders_by_list(self):
        t_a = Tag.objects.create(name="a", type=TagType.AFFECTED_REGION)
        t_b = Tag.objects.create(name="b", type=TagType.AFFECTED_REGION)
        ordered = sort_tags_with_overrides([t_a, t_b], [["b", "a"]])
        assert [t.name for t in ordered] == ["b", "a"]

    def test_multiple_groups_then_unpinned_alpha(self):
        t_us = Tag.objects.create(name="us", type=TagType.AFFECTED_REGION)
        t_eu = Tag.objects.create(name="eu", type=TagType.AFFECTED_REGION)
        t_de = Tag.objects.create(name="de", type=TagType.AFFECTED_REGION)
        t_zz = Tag.objects.create(name="zz", type=TagType.AFFECTED_REGION)
        ordered = sort_tags_with_overrides(
            [t_zz, t_de, t_eu, t_us],
            [["eu", "us"], ["de"]],
        )
        assert [t.name for t in ordered] == ["eu", "us", "de", "zz"]

    def test_tag_id_to_group_map(self):
        t_eu = Tag.objects.create(name="eu", type=TagType.AFFECTED_REGION)
        t_us = Tag.objects.create(name="us", type=TagType.AFFECTED_REGION)
        t_de = Tag.objects.create(name="de", type=TagType.AFFECTED_REGION)
        t_zz = Tag.objects.create(name="zz", type=TagType.AFFECTED_REGION)
        sorted_tags = sort_tags_with_overrides(
            [t_zz, t_de, t_eu, t_us],
            [["eu", "us"], ["de"]],
        )
        m = tag_id_to_group_map(sorted_tags, [["eu", "us"], ["de"]])
        assert m[t_eu.id] == 0
        assert m[t_us.id] == 0
        assert m[t_de.id] == 1
        assert m[t_zz.id] == 2

    def test_empty_groups_all_group_zero(self):
        t_a = Tag.objects.create(name="a", type=TagType.AFFECTED_REGION)
        m = tag_id_to_group_map([t_a], [])
        assert m[t_a.id] == 0
