from collections.abc import Sequence

from .models import Tag


def region_names_in_grouping(groups: list[list[str]]) -> set[str]:
    # looking for array of array, i.e. [[us, de], [disney, ly]]
    return {name for group in groups for name in group}


def _grouping_name_order_map(groups: list[list[str]]) -> dict[str, tuple[int, int]]:
    order: dict[str, tuple[int, int]] = {}
    for group_index, group in enumerate(groups):
        for position, name in enumerate(group):
            if name not in order:
                order[name] = (group_index, position)
    return order


def sort_tags_with_overrides(
    tags: Sequence[Tag], override_groups: list[list[str]]
) -> list[Tag]:
    if not override_groups:
        return list(tags)
    name_order = _grouping_name_order_map(override_groups)
    if not name_order:
        return list(tags)
    pinned_names = set(name_order.keys())
    pinned = [t for t in tags if t.name in pinned_names]
    pinned.sort(key=lambda t: name_order[t.name])
    rest = [t for t in tags if t.name not in pinned_names]
    return pinned + rest


def tag_id_to_group_map(
    sorted_tags: Sequence[Tag], groups: list[list[str]]
) -> dict[int, int]:
    if not groups:
        return {t.id: 0 for t in sorted_tags}
    name_to_group: dict[str, int] = {}
    for group_index, group in enumerate(groups):
        for name in group:
            if name not in name_to_group:
                name_to_group[name] = group_index
    unpinned_index = len(groups)
    return {t.id: name_to_group.get(t.name, unpinned_index) for t in sorted_tags}
