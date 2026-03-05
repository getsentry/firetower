from collections.abc import Sequence

from .models import Tag


def sort_tags_with_overrides(tags: Sequence[Tag], overrides: list[str]) -> list[Tag]:
    if not overrides:
        return list(tags)

    override_index = {name: i for i, name in enumerate(overrides)}
    pinned = []
    rest = []
    for tag in tags:
        if tag.name in override_index:
            pinned.append(tag)
        else:
            rest.append(tag)

    pinned.sort(key=lambda t: override_index[t.name])
    return pinned + rest
