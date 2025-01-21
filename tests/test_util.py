from pathlib import Path

from pathogena import util


def test_fail_command_exists() -> None:
    """Test that the `command_exists` function correctly identifies a non-existent command."""
    assert not util.command_exists("notarealcommandtest")


def test_find_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies duplicate entries in a list."""
    data = ["foo", "foo", "bar", "bar", "baz"]
    expected = ["foo", "bar"]
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == expected


def test_find_no_duplicate_entries() -> None:
    """Test that the `find_duplicate_entries` function correctly identifies that there are no duplicate entries in a list."""
    data = ["foo", "bar"]
    expected = []
    duplicates = util.find_duplicate_entries(data)
    assert duplicates == expected
