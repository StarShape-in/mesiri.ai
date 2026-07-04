import pytest

from mesiri_contracts.common import ErrorCategory, MesiriError, Result


def test_error_public_dict_is_redacted():
    err = MesiriError(
        error_code="X",
        category=ErrorCategory.PROVIDER,
        internal_message="secret db dsn leaked",
        user_safe_message="upstream failed",
    )
    pub = err.to_public_dict()
    assert "internal_message" not in pub
    assert pub["message"] == "upstream failed"


def test_result_err_unwrap_raises():
    r = Result.err(MesiriError(error_code="X", category=ErrorCategory.INTERNAL))
    assert r.is_err
    with pytest.raises(MesiriError):
        r.unwrap()
