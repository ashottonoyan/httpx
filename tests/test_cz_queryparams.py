"""
Pure in-memory unit tests for ``httpx.QueryParams``.

These tests construct ``QueryParams`` objects directly and exercise the
public surface area: construction from various inputs, multi-value key
handling, the immutable mutation helpers (``set``/``add``/``remove``/
``merge``), and equality / hashing behaviour. No network, no client,
no transport, no event loop.
"""

from __future__ import annotations

import pytest

import httpx


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construction_from_query_string():
    q = httpx.QueryParams("a=123&b=456")
    assert q["a"] == "123"
    assert q["b"] == "456"
    assert len(q) == 2


def test_construction_from_none_is_empty():
    q = httpx.QueryParams(None)
    assert len(q) == 0
    assert not q
    assert str(q) == ""


def test_construction_from_empty_string_is_empty():
    q = httpx.QueryParams("")
    assert len(q) == 0
    assert not q


def test_construction_from_no_args_is_empty():
    q = httpx.QueryParams()
    assert len(q) == 0
    assert not q


def test_construction_from_bytes_decodes_ascii():
    q = httpx.QueryParams(b"a=123&b=456")
    assert q["a"] == "123"
    assert q["b"] == "456"


def test_construction_from_dict():
    q = httpx.QueryParams({"a": "123", "b": "456"})
    assert q["a"] == "123"
    assert q["b"] == "456"


def test_construction_from_dict_with_list_value():
    q = httpx.QueryParams({"a": ["123", "456"], "b": "789"})
    assert q.get_list("a") == ["123", "456"]
    assert q["b"] == "789"


def test_construction_from_list_of_pairs():
    q = httpx.QueryParams([("a", "123"), ("a", "456"), ("b", "789")])
    assert q.get_list("a") == ["123", "456"]
    assert q["b"] == "789"


def test_construction_from_tuple_of_pairs():
    q = httpx.QueryParams((("a", "1"), ("b", "2")))
    assert q["a"] == "1"
    assert q["b"] == "2"


def test_construction_from_kwargs():
    q = httpx.QueryParams(a="1", b="2")
    assert q["a"] == "1"
    assert q["b"] == "2"


def test_construction_copies_from_existing_queryparams():
    source = httpx.QueryParams("a=1&a=2&b=3")
    copy = httpx.QueryParams(source)
    assert copy == source
    # Mutating-helpers on the copy must not affect the source.
    mutated = copy.set("a", "9")
    assert source.get_list("a") == ["1", "2"]
    assert mutated.get_list("a") == ["9"]


def test_construction_coerces_non_string_scalars():
    q = httpx.QueryParams({"a": 1, "b": True, "c": False, "d": None})
    assert q["a"] == "1"
    assert q["b"] == "true"
    assert q["c"] == "false"
    assert q["d"] == ""


def test_construction_keep_blank_values():
    q = httpx.QueryParams("a=&b=")
    assert q["a"] == ""
    assert q["b"] == ""


# ---------------------------------------------------------------------------
# Multi-value keys
# ---------------------------------------------------------------------------


def test_getitem_returns_first_value_for_repeated_key():
    q = httpx.QueryParams("a=123&a=456&b=789")
    assert q["a"] == "123"


def test_get_returns_first_value_for_repeated_key():
    q = httpx.QueryParams("a=123&a=456")
    assert q.get("a") == "123"


def test_get_returns_default_for_missing_key():
    q = httpx.QueryParams("a=123")
    assert q.get("missing") is None
    assert q.get("missing", "fallback") == "fallback"


def test_get_list_returns_all_values():
    q = httpx.QueryParams("a=123&a=456&b=789")
    assert q.get_list("a") == ["123", "456"]
    assert q.get_list("b") == ["789"]
    assert q.get_list("missing") == []


def test_keys_values_items_return_first_only():
    q = httpx.QueryParams("a=123&a=456&b=789")
    assert list(q.keys()) == ["a", "b"]
    assert list(q.values()) == ["123", "789"]
    assert list(q.items()) == [("a", "123"), ("b", "789")]


def test_multi_items_returns_every_pair():
    q = httpx.QueryParams("a=123&a=456&b=789")
    assert q.multi_items() == [("a", "123"), ("a", "456"), ("b", "789")]


def test_iter_yields_keys():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert list(iter(q)) == ["a", "b"]


def test_contains_and_len():
    q = httpx.QueryParams("a=1&b=2")
    assert "a" in q
    assert "b" in q
    assert "c" not in q
    assert len(q) == 2


# ---------------------------------------------------------------------------
# Immutability helpers
# ---------------------------------------------------------------------------


def test_set_returns_new_instance_and_does_not_mutate_original():
    original = httpx.QueryParams("a=123&b=456")
    updated = original.set("a", "999")

    assert updated is not original
    assert original["a"] == "123"
    assert updated["a"] == "999"
    assert updated["b"] == "456"


def test_set_replaces_all_values_for_repeated_key():
    q = httpx.QueryParams("a=1&a=2&a=3")
    updated = q.set("a", "X")
    assert updated.get_list("a") == ["X"]


def test_set_adds_a_brand_new_key():
    q = httpx.QueryParams("a=1")
    updated = q.set("b", "2")
    assert updated["a"] == "1"
    assert updated["b"] == "2"


def test_add_appends_value_for_existing_key():
    q = httpx.QueryParams("a=1")
    updated = q.add("a", "2")
    assert updated.get_list("a") == ["1", "2"]
    # original unchanged
    assert q.get_list("a") == ["1"]


def test_add_creates_key_when_missing():
    q = httpx.QueryParams("a=1")
    updated = q.add("b", "2")
    assert updated.get_list("b") == ["2"]


def test_remove_drops_key_entirely():
    q = httpx.QueryParams("a=1&a=2&b=3")
    updated = q.remove("a")

    assert "a" not in updated
    assert updated["b"] == "3"
    # original unchanged
    assert q.get_list("a") == ["1", "2"]


def test_remove_missing_key_is_noop():
    q = httpx.QueryParams("a=1")
    updated = q.remove("missing")
    assert updated == q
    assert updated is not q


def test_merge_adds_new_keys_and_overwrites_existing():
    q = httpx.QueryParams("a=1&b=2")
    merged = q.merge({"b": "20", "c": "3"})

    assert merged["a"] == "1"
    assert merged["b"] == "20"
    assert merged["c"] == "3"
    # original unchanged
    assert q["b"] == "2"
    assert "c" not in q


def test_merge_with_none_returns_copy():
    q = httpx.QueryParams("a=1")
    merged = q.merge(None)
    assert merged == q
    assert merged is not q


# ---------------------------------------------------------------------------
# Forbidden in-place mutation
# ---------------------------------------------------------------------------


def test_setitem_raises_runtime_error():
    q = httpx.QueryParams("a=1")
    with pytest.raises(RuntimeError):
        q["a"] = "2"


def test_update_raises_runtime_error():
    q = httpx.QueryParams("a=1")
    with pytest.raises(RuntimeError):
        q.update({"a": "2"})


# ---------------------------------------------------------------------------
# Equality, hashing, string representations
# ---------------------------------------------------------------------------


def test_equality_is_order_independent():
    a = httpx.QueryParams("a=1&b=2")
    b = httpx.QueryParams("b=2&a=1")
    assert a == b


def test_equality_with_multi_values_is_order_independent():
    a = httpx.QueryParams("a=1&a=2&b=3")
    b = httpx.QueryParams("b=3&a=2&a=1")
    assert a == b


def test_inequality_when_values_differ():
    a = httpx.QueryParams("a=1")
    b = httpx.QueryParams("a=2")
    assert a != b


def test_inequality_against_non_queryparams_object():
    q = httpx.QueryParams("a=1")
    assert q != "a=1"
    assert q != {"a": "1"}
    assert q != [("a", "1")]
    assert q != None  # noqa: E711 -- explicitly testing __eq__


def test_equal_instances_hash_equal():
    a = httpx.QueryParams("a=1&b=2")
    b = httpx.QueryParams("a=1&b=2")
    assert hash(a) == hash(b)
    # Usable as a dict key.
    bucket = {a: "value"}
    assert bucket[b] == "value"


def test_str_encodes_to_query_string():
    q = httpx.QueryParams([("a", "1"), ("a", "2"), ("b", "3")])
    assert str(q) == "a=1&a=2&b=3"


def test_str_percent_encodes_special_characters():
    q = httpx.QueryParams({"key": "a b&c=d"})
    encoded = str(q)
    # The reserved characters must be percent-encoded, not bare.
    assert "&c=d" not in encoded
    assert " " not in encoded
    # Round-trip should restore the original value.
    assert httpx.QueryParams(encoded)["key"] == "a b&c=d"


def test_repr_uses_class_name_and_query_string():
    q = httpx.QueryParams("a=1&b=2")
    assert repr(q) == "QueryParams('a=1&b=2')"


def test_bool_is_false_only_when_empty():
    assert not httpx.QueryParams()
    assert not httpx.QueryParams("")
    assert not httpx.QueryParams(None)
    assert httpx.QueryParams("a=1")
