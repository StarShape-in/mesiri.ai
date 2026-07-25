"""runtime/account_admin_parser.py — unit tests (pure, no I/O)."""

from __future__ import annotations

from runtime.account_admin_parser import parse_account_admin_command


def test_create_account_command():
    parsed = parse_account_admin_command("create account Site Cash")
    assert parsed is not None
    assert parsed.action == "create"
    assert parsed.fields == {"action": "create", "name": "Site Cash", "account_type": "cash"}


def test_create_account_is_case_insensitive():
    parsed = parse_account_admin_command("CREATE ACCOUNT Company Bank")
    assert parsed is not None
    assert parsed.fields["name"] == "Company Bank"


def test_rename_command():
    parsed = parse_account_admin_command("rename Site Cash to Kochi Site Cash")
    assert parsed is not None
    assert parsed.action == "rename"
    assert parsed.fields == {
        "action": "rename",
        "target_name": "Site Cash",
        "new_name": "Kochi Site Cash",
    }


def test_deactivate_command_with_account_keyword():
    parsed = parse_account_admin_command("deactivate account Company Bank")
    assert parsed is not None
    assert parsed.action == "deactivate"
    assert parsed.fields == {"action": "deactivate", "target_name": "Company Bank"}


def test_deactivate_command_without_account_keyword():
    parsed = parse_account_admin_command("deactivate Company Bank")
    assert parsed is not None
    assert parsed.fields == {"action": "deactivate", "target_name": "Company Bank"}


def test_unrecognized_text_returns_none():
    assert parse_account_admin_command("Spent 250 on fuel") is None
    assert parse_account_admin_command("how much cash do I have") is None


def test_blank_text_returns_none():
    assert parse_account_admin_command("   ") is None
    assert parse_account_admin_command("") is None


def test_create_account_with_no_name_returns_none():
    assert parse_account_admin_command("create account") is None


def test_rename_without_to_returns_none():
    assert parse_account_admin_command("rename Site Cash") is None
