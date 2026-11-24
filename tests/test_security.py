from app.security import csrf_matches, hash_password, new_csrf_token, verify_password


def test_passwords_are_hashed_never_plain():
    stored = hash_password("S3cret!pass")
    assert "S3cret" not in stored and stored.startswith("pbkdf2_sha256$")
    assert verify_password("S3cret!pass", stored)
    assert not verify_password("wrong", stored)
    assert hash_password("S3cret!pass") != stored  # random salt


def test_csrf_token_comparison():
    token = new_csrf_token()
    assert csrf_matches(token, token)
    assert not csrf_matches(token, "other") and not csrf_matches(None, token) and not csrf_matches(token, "")


def test_postgres_sql_translation_escapes_literal_percent_signs():
    from app.db import Database

    pg = Database.__new__(Database)  # no connection needed to test the translation
    pg.is_pg = True
    assert pg._sql("SELECT 1 FROM t WHERE k LIKE 'scan:%' AND id=:id") == "SELECT 1 FROM t WHERE k LIKE 'scan:%%' AND id=%(id)s"
