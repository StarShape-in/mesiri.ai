"""assert_downloadable_url — the guard against a memory:// URL reaching a browser.

Real incident: the fake object-storage adapter (local/test only, returns
`memory://...` links) got selected in a production-like deployment, and
every attendance/expense photo silently rendered as a broken image with an
`ERR_UNKNOWN_URL_SCHEME` console error and no server-side signal at all.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from mesiri.domains.shared.media import assert_downloadable_url


@pytest.mark.parametrize("url", ["https://example.com/a.jpg", "http://example.com/a.jpg"])
def test_http_and_https_urls_pass_through_unchanged(url):
    assert assert_downloadable_url(url) == url


def test_a_memory_scheme_url_raises_instead_of_reaching_the_response():
    with pytest.raises(HTTPException) as exc_info:
        assert_downloadable_url("memory://media/wamid.abc?expires_in=600&method=GET")
    assert exc_info.value.status_code == 500
