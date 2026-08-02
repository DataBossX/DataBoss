"""Tests for the real Drive client, driven entirely through a fake transport.

No network is touched. The transport is a plain callable, so every branch --
pagination, native-doc export, append-only refusal, outage classification,
token scrubbing -- is exercised deterministically.
"""

import json

import pytest

from control_tower.constants import ControlTowerError
from control_tower.drive import DriveOutage
from control_tower.drive_google import (
    DriveApiError,
    DriveAuthMissing,
    GoogleDriveClient,
)
from control_tower.safety import UntrustedUrl

TOKEN = "test-token-not-a-real-credential"


class FakeTransport:
    """Records requests and replays queued responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected extra request to {0}".format(request.full_url))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def ok(payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    return (200, {}, body)


def client(responses):
    transport = FakeTransport(responses)
    return GoogleDriveClient(access_token=TOKEN, transport=transport), transport


# --- auth -----------------------------------------------------------------
def test_missing_token_raises_before_any_request(monkeypatch):
    monkeypatch.delenv("DBX_DRIVE_ACCESS_TOKEN", raising=False)
    transport = FakeTransport([])
    c = GoogleDriveClient(access_token=None, transport=transport)
    with pytest.raises(DriveAuthMissing):
        c.get_metadata("FILEID")
    assert transport.requests == [], "no request may be attempted without a token"


def test_token_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("DBX_DRIVE_ACCESS_TOKEN", TOKEN)
    c = GoogleDriveClient(transport=FakeTransport([ok({"id": "X", "name": "n", "parents": []})]))
    assert c.get_metadata("X")["id"] == "X"


def test_token_is_sent_as_bearer_header():
    c, transport = client([ok({"id": "X", "name": "n", "parents": []})])
    c.get_metadata("X")
    assert transport.requests[0].get_header("Authorization") == "Bearer {0}".format(TOKEN)


# --- URL trust ------------------------------------------------------------
def test_every_request_url_is_on_a_trusted_host(monkeypatch):
    monkeypatch.setattr("control_tower.drive_google.DRIVE_API", "https://docichat.com/drive/v3")
    c, _t = client([ok({})])
    with pytest.raises(UntrustedUrl):
        c.get_metadata("X")


def test_requests_go_to_googleapis():
    c, transport = client([ok({"id": "X", "name": "n", "parents": []})])
    c.get_metadata("X")
    assert transport.requests[0].full_url.startswith("https://www.googleapis.com/drive/v3")


# --- normalisation --------------------------------------------------------
def test_v3_shape_is_normalised_to_the_towers_shape():
    c, _t = client([ok({"id": "A", "name": "title.json", "parents": ["P"], "size": "12"})])
    meta = c.get_metadata("A")
    assert meta["id"] == "A"
    assert meta["title"] == "title.json"
    assert meta["parentId"] == "P"
    assert meta["fileSize"] == "12"


def test_missing_parents_normalises_to_none():
    c, _t = client([ok({"id": "A", "name": "n", "parents": []})])
    assert c.get_metadata("A")["parentId"] is None


# --- listing and pagination ----------------------------------------------
def test_list_children_follows_pagination():
    page1 = ok({"files": [{"id": "1", "name": "a", "parents": ["F"]}], "nextPageToken": "t2"})
    page2 = ok({"files": [{"id": "2", "name": "b", "parents": ["F"]}]})
    c, transport = client([page1, page2])
    children = c.list_children("F")
    assert [x["id"] for x in children] == ["1", "2"]
    assert "pageToken=t2" in transport.requests[1].full_url


def test_list_children_excludes_trashed_in_query():
    c, transport = client([ok({"files": []})])
    c.list_children("FOLDER")
    assert "trashed" in transport.requests[0].full_url


# --- download -------------------------------------------------------------
def test_binary_download_uses_alt_media():
    meta = ok({"id": "A", "name": "r.json", "parents": ["P"], "mimeType": "application/json"})
    c, transport = client([meta, (200, {}, b'{"exact":"bytes"}')])
    assert c.download("A") == b'{"exact":"bytes"}'
    assert "alt=media" in transport.requests[1].full_url


def test_google_native_doc_is_exported_not_fetched():
    meta = ok(
        {
            "id": "D",
            "name": "doc",
            "parents": ["P"],
            "mimeType": "application/vnd.google-apps.document",
        }
    )
    c, transport = client([meta, (200, {}, b"exported text")])
    assert c.download("D") == b"exported text"
    url = transport.requests[1].full_url
    assert "/export?" in url and "text%2Fplain" in url


# --- append-only ----------------------------------------------------------
def test_create_refuses_when_the_name_already_exists():
    existing = ok({"files": [{"id": "OLD", "name": "r.json", "parents": ["F"]}]})
    c, transport = client([existing])
    with pytest.raises(ControlTowerError) as excinfo:
        c.create("F", "r.json", b"{}", "application/json")
    assert "append-only" in str(excinfo.value)
    assert len(transport.requests) == 1, "must not attempt the upload after refusing"


def test_create_uploads_when_the_name_is_free():
    c, transport = client(
        [ok({"files": []}), ok({"id": "NEW", "name": "r.json", "parents": ["F"], "size": "2"})]
    )
    created = c.create("F", "r.json", b"{}", "application/json")
    assert created["id"] == "NEW"
    assert transport.requests[1].full_url.startswith(
        "https://www.googleapis.com/upload/drive/v3/files"
    )
    assert "uploadType=multipart" in transport.requests[1].full_url


def test_uploaded_body_carries_the_exact_payload_bytes():
    payload = b'{"a": 1, "hold": "FOR REVIEW - HOLD NO EXTERNAL RELEASE"}'
    c, transport = client([ok({"files": []}), ok({"id": "N", "name": "r.json", "parents": ["F"]})])
    c.create("F", "r.json", payload, "application/json")
    assert payload in transport.requests[1].data


def test_find_by_name_escapes_quotes_in_the_query():
    c, transport = client([ok({"files": []})])
    c.find_by_name("F", "weird'name.json")
    assert "%5C%27" in transport.requests[0].full_url or "\\'" in transport.requests[0].full_url


# --- error classification -------------------------------------------------
@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_transient_statuses_are_outages_so_evidence_survives(status):
    c, _t = client([(status, {}, b"upstream sad")])
    with pytest.raises(DriveOutage):
        c.get_metadata("A")


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_api_errors_not_outages(status):
    c, _t = client([(status, {}, b'{"error":"denied"}')])
    with pytest.raises(DriveApiError):
        c.get_metadata("A")


def test_network_failure_is_reported_as_an_outage():
    """A dead network must classify as an outage, not an API error.

    The distinction is load-bearing: an outage means spooled evidence is
    retained and the run can be completed later, whereas an API error means
    Drive answered and refused.
    """
    import urllib.error

    c, _t = client([urllib.error.URLError("no route to host")])
    with pytest.raises(DriveOutage):
        c.get_metadata("A")


def test_default_transport_surfaces_http_status_rather_than_raising(monkeypatch):
    """HTTPError carries the status we classify on, so it must not escape."""
    import urllib.error

    def boom(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 404, "gone", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", boom)
    c = GoogleDriveClient(access_token=TOKEN)
    with pytest.raises(DriveApiError):
        c.get_metadata("A")


@pytest.mark.parametrize(
    "secret",
    [
        "ya29." + "A" * 40,          # matches a known credential pattern
        "opaque-session-value-9182",  # matches nothing; only value-scrubbing saves it
    ],
    ids=["pattern_matched", "opaque"],
)
def test_error_messages_never_carry_the_token_even_when_opaque(secret):
    c = GoogleDriveClient(
        access_token=secret,
        transport=FakeTransport([(403, {}, b'{"error":"token=' + secret.encode() + b'"}')]),
    )
    with pytest.raises(DriveApiError) as excinfo:
        c.get_metadata("A")
    assert secret not in str(excinfo.value)


def test_error_messages_never_carry_the_token():
    secret = "ya29." + "A" * 40
    c = GoogleDriveClient(
        access_token=secret,
        transport=FakeTransport([(403, {}, b'{"error":"token=' + secret.encode() + b'"}')]),
    )
    with pytest.raises(DriveApiError) as excinfo:
        c.get_metadata("A")
    assert secret not in str(excinfo.value)


def test_non_json_response_is_reported_clearly():
    c, _t = client([(200, {}, b"<html>not json</html>")])
    with pytest.raises(DriveApiError):
        c.get_metadata("A")


# --- interface conformance ------------------------------------------------
def test_satisfies_the_drive_client_interface():
    from control_tower.drive import DriveClient

    assert issubclass(GoogleDriveClient, DriveClient)
    for method in ("list_children", "get_metadata", "download", "create", "find_by_name"):
        assert callable(getattr(GoogleDriveClient, method))
