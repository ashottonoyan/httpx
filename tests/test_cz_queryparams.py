"""
Pure unit tests for httpx.QueryParams.

Network-free, transport-free, event-loop-free coverage of the public
QueryParams type: construction, multi-value behaviour, immutability
helpers, value coercion, equality, hashing, and representation.
"""

from __future__ import annotations

import pytest

import httpx


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_construct_empty():
    q = httpx.QueryParams()
    assert len(q) == 0
    assert bool(q) is False
    assert list(q.keys()) == []
    assert str(q) == ""


def test_construct_from_none():
    q = httpx.QueryParams(None)
    assert len(q) == 0
    assert str(q) == ""


def test_construct_from_string():
    q = httpx.QueryParams("a=1&b=2")
    assert list(q.items()) == [("a", "1"), ("b", "2")]


def test_construct_from_bytes():
    q = httpx.QueryParams(b"a=1&b=2")
    assert list(q.items()) == [("a", "1"), ("b", "2")]


def test_construct_from_dict():
    q = httpx.QueryParams({"a": "1", "b": "2"})
    assert q["a"] == "1"
    assert q["b"] == "2"


def test_construct_from_list_of_pairs():
    q = httpx.QueryParams([("a", "1"), ("b", "2"), ("a", "3")])
    assert q.get_list("a") == ["1", "3"]
    assert q.get_list("b") == ["2"]


def test_construct_from_tuple_of_pairs():
    q = httpx.QueryParams((("a", "1"), ("b", "2")))
    assert list(q.items()) == [("a", "1"), ("b", "2")]


def test_construct_from_kwargs():
    q = httpx.QueryParams(a="1", b="2")
    assert q["a"] == "1"
    assert q["b"] == "2"


def test_construct_copy_from_queryparams():
    src = httpx.QueryParams("a=1&a=2&b=3")
    dst = httpx.QueryParams(src)
    assert dst == src
    # Verify it is a deep-enough copy: mutating dst's internal lists must
    # not affect src.
    dst._dict["a"].append("99")
    assert src.get_list("a") == ["1", "2"]


def test_construct_keeps_blank_values():
    q = httpx.QueryParams("a=&b=2")
    assert q["a"] == ""
    assert q["b"] == "2"


# ---------------------------------------------------------------------------
# Value coercion
# ---------------------------------------------------------------------------


def test_coerce_bool_values():
    q = httpx.QueryParams({"yes": True, "no": False})
    assert q["yes"] == "true"
    assert q["no"] == "false"


def test_coerce_none_value_to_empty_string():
    q = httpx.QueryParams({"a": None})
    assert q["a"] == ""


def test_coerce_int_and_float_values():
    q = httpx.QueryParams({"i": 7, "f": 1.5})
    assert q["i"] == "7"
    assert q["f"] == "1.5"


def test_coerce_non_string_keys():
    q = httpx.QueryParams({1: "one"})
    # Integer keys are coerced to strings.
    assert q["1"] == "one"
    assert "1" in q


# ---------------------------------------------------------------------------
# Multi-value key behaviour
# ---------------------------------------------------------------------------


def test_multi_value_get_returns_first():
    q = httpx.QueryParams("a=1&a=2&a=3")
    assert q.get("a") == "1"
    assert q["a"] == "1"


def test_multi_value_get_list_returns_all():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert q.get_list("a") == ["1", "2"]
    assert q.get_list("b") == ["3"]


def test_get_list_missing_key_returns_empty_list():
    q = httpx.QueryParams("a=1")
    assert q.get_list("missing") == []


def test_get_default_when_missing():
    q = httpx.QueryParams("a=1")
    assert q.get("missing") is None
    assert q.get("missing", "fallback") == "fallback"


def test_items_returns_one_pair_per_key():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert list(q.items()) == [("a", "1"), ("b", "3")]


def test_multi_items_preserves_duplicates():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert q.multi_items() == [("a", "1"), ("a", "2"), ("b", "3")]


def test_keys_and_values_views():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert list(q.keys()) == ["a", "b"]
    assert list(q.values()) == ["1", "3"]


def test_dict_from_list_with_list_value():
    q = httpx.QueryParams({"a": ["1", "2"], "b": "3"})
    assert q.get_list("a") == ["1", "2"]
    assert q.get_list("b") == ["3"]


# ---------------------------------------------------------------------------
# Immutability helpers
# ---------------------------------------------------------------------------


def test_set_returns_new_instance_with_replaced_value():
    q1 = httpx.QueryParams("a=1&a=2&b=3")
    q2 = q1.set("a", "999")
    assert q2 is not q1
    assert q2.get_list("a") == ["999"]
    # Original is untouched.
    assert q1.get_list("a") == ["1", "2"]


def test_set_adds_new_key_when_missing():
    q1 = httpx.QueryParams("a=1")
    q2 = q1.set("b", "2")
    assert q2.get_list("b") == ["2"]
    assert "b" not in q1


def test_add_appends_value_to_existing_key():
    q1 = httpx.QueryParams("a=1")
    q2 = q1.add("a", "2")
    assert q2.get_list("a") == ["1", "2"]
    # Original untouched.
    assert q1.get_list("a") == ["1"]


def test_add_creates_key_when_missing():
    q1 = httpx.QueryParams("a=1")
    q2 = q1.add("b", "2")
    assert q2.get_list("b") == ["2"]
    assert "b" not in q1


def test_remove_drops_all_values_for_key():
    q1 = httpx.QueryParams("a=1&a=2&b=3")
    q2 = q1.remove("a")
    assert "a" not in q2
    assert q2.get_list("b") == ["3"]
    # Original untouched.
    assert q1.get_list("a") == ["1", "2"]


def test_remove_missing_key_is_noop():
    q1 = httpx.QueryParams("a=1")
    q2 = q1.remove("missing")
    assert q2 == q1
    assert q2 is not q1


def test_merge_adds_new_keys():
    q1 = httpx.QueryParams("a=1")
    q2 = q1.merge({"b": "2"})
    assert q2 == httpx.QueryParams("a=1&b=2")


def test_merge_overwrites_existing_keys():
    q1 = httpx.QueryParams("a=1&b=2")
    q2 = q1.merge({"a": "999"})
    assert q2.get_list("a") == ["999"]
    assert q2.get_list("b") == ["2"]


def test_merge_none_returns_equivalent_copy():
    q1 = httpx.QueryParams("a=1&b=2")
    q2 = q1.merge(None)
    assert q2 == q1


def test_update_raises_runtime_error():
    q = httpx.QueryParams("a=1")
    with pytest.raises(RuntimeError):
        q.update({"a": "2"})


def test_setitem_raises_runtime_error():
    q = httpx.QueryParams("a=1")
    with pytest.raises(RuntimeError):
        q["a"] = "2"


# ---------------------------------------------------------------------------
# Equality, hashing, containment
# ---------------------------------------------------------------------------


def test_equality_ignores_order():
    a = httpx.QueryParams("a=1&b=2")
    b = httpx.QueryParams("b=2&a=1")
    assert a == b


def test_equality_respects_duplicate_count():
    a = httpx.QueryParams("a=1&a=2")
    b = httpx.QueryParams("a=1")
    assert a != b


def test_equality_against_non_queryparams_is_false():
    q = httpx.QueryParams("a=1")
    assert q != "a=1"
    assert q != {"a": "1"}
    assert q != [("a", "1")]


def test_hash_is_consistent_with_string_form():
    q = httpx.QueryParams("a=1&b=2")
    assert hash(q) == hash(str(q))


def test_hashable_in_set():
    q1 = httpx.QueryParams("a=1")
    q2 = httpx.QueryParams("a=1")
    assert {q1, q2} == {q1}


def test_contains_and_len_and_bool():
    q = httpx.QueryParams("a=1&b=2")
    assert "a" in q
    assert "missing" not in q
    assert len(q) == 2
    assert bool(q) is True


def test_iter_yields_keys_only():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert list(iter(q)) == ["a", "b"]


# ---------------------------------------------------------------------------
# String / repr
# ---------------------------------------------------------------------------


def test_str_round_trip():
    q = httpx.QueryParams("a=1&a=2&b=3")
    assert str(q) == "a=1&a=2&b=3"


def test_str_url_encodes_special_chars():
    q = httpx.QueryParams({"q": "hello world"})
    # urlencode uses "+" for spaces.
    assert str(q) == "q=hello+world"


def test_repr_format():
    q = httpx.QueryParams("a=1&b=2")
    assert repr(q) == "QueryParams('a=1&b=2')"
