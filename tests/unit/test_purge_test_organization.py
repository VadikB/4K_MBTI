import pytest

from scripts.purge_test_organization import (
    ForeignKey,
    USER_OWNERSHIP_COLUMNS,
    _delete_order,
    require_test_database,
)


def test_database_guard_accepts_only_test_names():
    assert require_test_database("postgresql://user:pass@localhost/agent4k_test") == "agent4k_test"
    assert require_test_database("postgresql://user:pass@localhost/product4k_pytest_1") == "product4k_pytest_1"
    with pytest.raises(ValueError, match="test or pytest"):
        require_test_database("postgresql://user:pass@localhost/agent4k")


def test_delete_order_places_children_before_parents():
    foreign_keys = [
        ForeignKey(parent_oid=1, child_oid=2, parent_columns=("id",), child_columns=("root_id",)),
        ForeignKey(parent_oid=2, child_oid=3, parent_columns=("id",), child_columns=("child_id",)),
    ]
    assert _delete_order({1, 2, 3}, foreign_keys) == [3, 2, 1]


def test_delete_order_rejects_cross_table_cycle():
    foreign_keys = [
        ForeignKey(parent_oid=1, child_oid=2, parent_columns=("id",), child_columns=("one_id",)),
        ForeignKey(parent_oid=2, child_oid=1, parent_columns=("id",), child_columns=("two_id",)),
    ]
    with pytest.raises(RuntimeError, match="Cyclic"):
        _delete_order({1, 2}, foreign_keys)


def test_only_explicit_account_relationships_are_ownership_edges():
    assert "user_id" in USER_OWNERSHIP_COLUMNS
    assert "owner_user_id" in USER_OWNERSHIP_COLUMNS
    assert "recipient_user_id" in USER_OWNERSHIP_COLUMNS
    assert "created_by_user_id" not in USER_OWNERSHIP_COLUMNS
    assert "uploaded_by_user_id" not in USER_OWNERSHIP_COLUMNS
    assert "connected_by_user_id" not in USER_OWNERSHIP_COLUMNS
    assert "future_actor_reference" not in USER_OWNERSHIP_COLUMNS
