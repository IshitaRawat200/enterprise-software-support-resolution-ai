from app.sql.sql_validator import SQLValidationError, SQLValidator


def test_validate_allows_select_and_with_and_appends_limit():
    v = SQLValidator()

    sql = "SELECT id FROM users"
    normalized = v.validate(sql)
    assert "LIMIT 50" in normalized

    sql_with_with = "WITH cte AS (SELECT 1) SELECT * FROM users"
    normalized2 = v.validate(sql_with_with)
    assert "WITH" in normalized2


def test_validate_forbids_keywords():
    v = SQLValidator()

    bad_sql = "SELECT * FROM users; DROP TABLE users"
    try:
        v.validate(bad_sql)
    except SQLValidationError:
        assert True
    else:
        assert False, "Expected SQLValidationError for forbidden keyword"


def test_validate_disallows_multiple_statements_and_invalid_start():
    v = SQLValidator()

    import pytest

    with pytest.raises(SQLValidationError):
        v.validate("")

    with pytest.raises(SQLValidationError):
        v.validate("INSERT INTO users (id) VALUES (1)")
