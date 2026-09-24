from flightops.init_db import list_sql_files


def test_sql_files_are_numbered_and_ordered():
    names = [p.name for p in list_sql_files()]
    assert names == sorted(names)
    assert names[0].startswith("00_")
    assert len(names) == 5


def test_sql_files_contain_no_percent_signs():
    # A percent sign can confuse the database driver's parameter handling.
    for path in list_sql_files():
        assert "%" not in path.read_text(encoding="utf-8"), path.name