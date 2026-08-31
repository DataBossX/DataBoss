"""A real Google Drive client for the Control Tower, standard library only.

This speaks the Drive v3 REST API over ``urllib`` so the tower keeps its
no-dependency property and can run on the authorized Windows workstation with
nothing but Python installed.

Three things here are load-bearing:

**Create never replaces.** Drive's API will happily create a second file with
the same name in the same folder, and an ``update`` call would overwrite bytes
outright. Neither is acceptable for an append-only control package, so
``create`` checks for an existing name first and refuses rather than racing.

**Every request URL is checked against the trusted-host allowlist** before it
is opened. Drive metadata has been observed carrying third-party URLs; nothing
here ever follows a URL that came back in a response body.

**The access token never reaches a log, an exception, or a receipt.** It lives
in one header and is scrubbed from every error path.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .constants import ControlTowerError
from .drive import DriveClient, DriveOutage
from .safety import REDACTED, assert_trusted_url, redact

DRIVE_API = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD_API = "https://www.googleapis.com/upload/drive/v3"

# Google-native documents have no byte stream to download; they must be
# exported. Anything else is fetched verbatim with alt=media.
_NATIVE_EXPORT = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_FIELDS = "id,name,parents,mimeType,size,md5Checksum,version,createdTime,modifiedTime"


class DriveAuthMissing(ControlTowerError):
    """No access token was supplied, so no request was attempted."""


class DriveApiError(ControlTowerError):
    """Drive returned an error. The message is redacted before it propagates."""


def _scrub(text, token=None):
    """Never let a credential escape in an error message.

    Pattern-based redaction alone is not enough here. A Drive access token can
    be an opaque string that matches no known credential shape, so the exact
    token this client holds is removed by value first, and the generic
    patterns are applied afterwards to catch anything else in the payload.
    """
    out = str(text)
    if token:
        out = out.replace(token, REDACTED)
    return redact(out)


class GoogleDriveClient(DriveClient):
    """Drive v3 over urllib.

    ``transport`` exists so the whole client is testable without a network:
    it is called as ``transport(request) -> (status, headers, body_bytes)``.
    """

    def __init__(self, access_token=None, transport=None, timeout=60):
        self._token = access_token or os.environ.get("DBX_DRIVE_ACCESS_TOKEN")
        self._transport = transport or self._urllib_transport
        self.timeout = timeout

    # -- plumbing ---------------------------------------------------------
    def _urllib_transport(self, request):
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status, dict(response.headers), response.read()
        except urllib.error.HTTPError as exc:
            body = b""
            try:
                body = exc.read()
            except Exception:  # noqa: BLE001 - body is best effort
                pass
            return exc.code, dict(exc.headers or {}), body

    def _request(self, method, url, body=None, content_type=None):
        if not self._token:
            raise DriveAuthMissing(
                "no Drive access token; set DBX_DRIVE_ACCESS_TOKEN before running"
            )
        assert_trusted_url(url)
        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", "Bearer {0}".format(self._token))
        if content_type:
            request.add_header("Content-Type", content_type)
        try:
            status, _headers, payload = self._transport(request)
        except urllib.error.URLError as exc:
            # No route, DNS failure, TLS failure: the surface is unreachable.
            # This is an outage, not a permission problem, and the caller's
            # spooled evidence must survive it. Converting here rather than
            # inside the default transport means any injected transport gets
            # the same classification.
            raise DriveOutage("Drive unreachable: {0}".format(_scrub(exc.reason, self._token))) from None
        if status in (429, 500, 502, 503, 504):
            raise DriveOutage("Drive returned {0}".format(status))
        if status >= 400:
            raise DriveApiError(
                "Drive {0} on {1}: {2}".format(
                    status, urllib.parse.urlparse(url).path, _scrub(payload[:400], self._token)
                )
            )
        return payload

    def _json(self, method, url, body=None, content_type=None):
        payload = self._request(method, url, body=body, content_type=content_type)
        if not payload:
            return {}
        try:
            return json.loads(payload.decode("utf-8"))
        except ValueError as exc:
            raise DriveApiError("Drive returned non-JSON: {0}".format(_scrub(exc, self._token))) from None

    @staticmethod
    def _normalise(item):
        """Map Drive v3 shape onto the shape the rest of the tower expects."""
        parents = item.get("parents") or []
        return {
            "id": item.get("id"),
            "parentId": parents[0] if parents else None,
            "title": item.get("name"),
            "mimeType": item.get("mimeType"),
            "fileSize": item.get("size"),
            "md5Checksum": item.get("md5Checksum"),
            "version": item.get("version"),
            "createdTime": item.get("createdTime"),
            "modifiedTime": item.get("modifiedTime"),
        }

    # -- DriveClient ------------------------------------------------------
    def list_children(self, folder_id):
        out = []
        page_token = None
        while True:
            params = {
                "q": "'{0}' in parents and trashed = false".format(folder_id),
                "fields": "nextPageToken,files({0})".format(_FIELDS),
                "pageSize": "200",
            }
            if page_token:
                params["pageToken"] = page_token
            url = "{0}/files?{1}".format(DRIVE_API, urllib.parse.urlencode(params))
            data = self._json("GET", url)
            out.extend(self._normalise(f) for f in data.get("files", []))
            page_token = data.get("nextPageToken")
            if not page_token:
                return out

    def get_metadata(self, file_id):
        url = "{0}/files/{1}?{2}".format(
            DRIVE_API,
            urllib.parse.quote(file_id, safe=""),
            urllib.parse.urlencode({"fields": _FIELDS}),
        )
        return self._normalise(self._json("GET", url))

    def download(self, file_id):
        """Return exact bytes. Google-native docs are exported, not fetched."""
        meta = self.get_metadata(file_id)
        export_as = _NATIVE_EXPORT.get(meta.get("mimeType"))
        quoted = urllib.parse.quote(file_id, safe="")
        if export_as:
            url = "{0}/files/{1}/export?{2}".format(
                DRIVE_API, quoted, urllib.parse.urlencode({"mimeType": export_as})
            )
        else:
            url = "{0}/files/{1}?alt=media".format(DRIVE_API, quoted)
        return self._request("GET", url)

    def find_by_name(self, folder_id, name):
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        params = {
            "q": "'{0}' in parents and name = '{1}' and trashed = false".format(
                folder_id, escaped
            ),
            "fields": "files({0})".format(_FIELDS),
            "pageSize": "10",
        }
        url = "{0}/files?{1}".format(DRIVE_API, urllib.parse.urlencode(params))
        files = self._json("GET", url).get("files", [])
        return self._normalise(files[0]) if files else None

    def create(self, folder_id, name, payload, mime_type):
        """Create a new file. Refuses to replace an existing name.

        Append-only has to be enforced here, at the storage boundary, rather
        than left to the caller's good intentions.
        """
        if self.find_by_name(folder_id, name) is not None:
            raise ControlTowerError(
                "append-only: a file named {0} already exists in {1}".format(name, folder_id)
            )

        metadata = {"name": name, "parents": [folder_id], "mimeType": mime_type}
        boundary = "==databossx-control-tower-boundary=="
        parts = [
            "--{0}".format(boundary),
            "Content-Type: application/json; charset=UTF-8",
            "",
            json.dumps(metadata),
            "--{0}".format(boundary),
            "Content-Type: {0}".format(mime_type),
            "",
            "",
        ]
        body = "\r\n".join(parts).encode("utf-8") + bytes(payload)
        body += "\r\n--{0}--\r\n".format(boundary).encode("utf-8")

        url = "{0}/files?{1}".format(
            DRIVE_UPLOAD_API,
            urllib.parse.urlencode({"uploadType": "multipart", "fields": _FIELDS}),
        )
        created = self._json(
            "POST",
            url,
            body=body,
            content_type='multipart/related; boundary="{0}"'.format(boundary),
        )
        return self._normalise(created)
