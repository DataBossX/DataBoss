// Centralized API client: base URL, optional API key, and error parsing.
// REACT_APP_API_KEY is sent as X-API-Key when the backend has auth enabled.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const API_KEY = process.env.REACT_APP_API_KEY || '';

// File types the backend can actually extract text from (text + images).
export const SUPPORTED_ACCEPT =
  '.txt,.md,.csv,.json,.xml,.html,.png,.jpg,.jpeg,.bmp,.tiff,.webp,.gif';

function authHeaders(extra = {}) {
  const h = { ...extra };
  if (API_KEY) h['X-API-Key'] = API_KEY;
  return h;
}

async function parseError(res) {
  let message = `Request failed (${res.status})`;
  try {
    const data = await res.json();
    if (data && data.error) message = data.error;
  } catch (_) {
    /* non-JSON body */
  }
  const err = new Error(message);
  err.status = res.status;
  return err;
}

export async function apiGet(path) {
  const res = await fetch(`${BACKEND_URL}${path}`, { headers: authHeaders() });
  if (!res.ok) throw await parseError(res);
  return res.json();
}

export async function apiUpload(path, formData) {
  // Do not set Content-Type; the browser sets the multipart boundary.
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  });
  if (!res.ok) throw await parseError(res);
  return res.json();
}
