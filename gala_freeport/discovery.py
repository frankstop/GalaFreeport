from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .models import CATEGORY_TREE_ID, CategoryLeaf
from .parsers import ContractError


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    tree_id: str
    leaves: tuple[CategoryLeaf, ...]
    roots: tuple[CategoryLeaf, ...]
    total_nodes: int
    root_nodes: int
    leaf_nodes: int


def _children(node: dict[str, Any]) -> list[dict[str, Any]]:
    value = node.get("List")
    if not isinstance(value, list):
        raise ContractError("category node List must be an array")
    return [child for child in value if isinstance(child, dict)]


def _node_id(node: dict[str, Any]) -> str:
    value = node.get("Id")
    if value is None or str(value).strip() == "":
        raise ContractError("category node is missing Id")
    return str(value)


def _node_name(node: dict[str, Any]) -> str:
    value = " ".join(str(node.get("N") or "").split())
    if not value:
        raise ContractError(f"category {_node_id(node)} is missing N")
    return value


def walk_categories(
    nodes: Iterable[dict[str, Any]],
    path_names: tuple[str, ...] = (),
    path_ids: tuple[str, ...] = (),
):
    for node in nodes:
        identifier = _node_id(node)
        name = _node_name(node)
        next_names = path_names + (name,)
        next_ids = path_ids + (identifier,)
        yield node, next_names, next_ids
        yield from walk_categories(_children(node), next_names, next_ids)


def discover_leaves(category_tree: Any) -> DiscoveryResult:
    """Validate the My Cloud Grocer tree and select every live leaf dynamically."""
    if not isinstance(category_tree, list) or not category_tree:
        raise ContractError("category tree response must be a non-empty array")
    roots = [node for node in category_tree if isinstance(node, dict)]
    if len(roots) != len(category_tree):
        raise ContractError("category tree contains non-object roots")
    walked = list(walk_categories(roots))
    leaves = [
        CategoryLeaf(_node_id(node), _node_name(node), names, ids)
        for node, names, ids in walked
        if not _children(node)
    ]
    if not leaves:
        raise ContractError("category tree contains no leaf categories")
    ids = [leaf.category_id for leaf in leaves]
    if len(ids) != len(set(ids)):
        raise ContractError("category tree contains duplicate leaf IDs")
    return DiscoveryResult(
        tree_id=CATEGORY_TREE_ID,
        leaves=tuple(leaves),
        roots=tuple(leaves),
        total_nodes=len(walked),
        root_nodes=len(roots),
        leaf_nodes=len(leaves),
    )


def find_category(category_tree: Any, category_id: str) -> CategoryLeaf:
    discovery = discover_leaves(category_tree)
    for leaf in discovery.leaves:
        if leaf.category_id == str(category_id):
            return leaf
    raise ContractError(f"category {category_id} is not a current leaf in the Freeport–Merrick tree")
