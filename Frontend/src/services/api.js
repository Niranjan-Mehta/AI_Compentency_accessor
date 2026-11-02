const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api').replace(/\/$/, '');

function tokenStore() {
  return localStorage.getItem('assessor.access') || sessionStorage.getItem('assessor.access')
    ? localStorage.getItem('assessor.access') ? localStorage : sessionStorage
    : sessionStorage;
}

export function getAccessToken() {
  return tokenStore().getItem('assessor.access');
}

function getRefreshToken() {
  return tokenStore().getItem('assessor.refresh');
}

function saveTokens(tokens, persist = false) {
  clearTokens();
  const store = persist ? localStorage : sessionStorage;
  if (tokens.access) store.setItem('assessor.access', tokens.access);
  if (tokens.refresh) store.setItem('assessor.refresh', tokens.refresh);
}

export function clearTokens() {
  for (const store of [localStorage, sessionStorage]) {
    store.removeItem('assessor.access');
    store.removeItem('assessor.refresh');
  }
}

export function hasSession() {
  return Boolean(getAccessToken() && getRefreshToken());
}

function explainError(payload, statusCode) {
  if (typeof payload === 'string') return payload;
  if (payload?.detail) return payload.detail;
  if (payload?.error) return payload.error;
  if (payload && typeof payload === 'object') {
    const first = Object.entries(payload)[0];
    if (first) {
      const detail = Array.isArray(first[1]) ? first[1][0] : first[1];
      return `${first[0]}: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`;
    }
  }
  return `Request failed (${statusCode}).`;
}

async function refreshAccessToken() {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh }),
    });
    const result = await response.json();
    if (!response.ok || !result.access) throw new Error('Session expired. Please sign in again.');
    const persistent = localStorage.getItem('assessor.refresh') !== null;
    saveTokens({ access: result.access, refresh: result.refresh || refresh }, persistent);
    return true;
  } catch {
    clearTokens();
    window.dispatchEvent(new CustomEvent('assessor:session-expired'));
    return false;
  }
}

async function request(path, options = {}, retry = true) {
  const url = /^https?:\/\//.test(path) ? path : `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new Error(`Cannot reach the backend at ${API_BASE_URL}. Check that Django is running and the API URL is correct.`);
  }
  if (response.status === 401 && retry && !path.includes('/auth/token/refresh/')) {
    if (await refreshAccessToken()) return request(path, options, false);
  }
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : await response.text();
  if (!response.ok) throw new Error(explainError(payload, response.status));
  return payload;
}

const json = (method, value) => ({ method, body: JSON.stringify(value) });

export const api = {
  baseUrl: API_BASE_URL,
  request,
  async login(identifier, password, remember = false) {
    const tokens = await request('/auth/login/', json('POST', { username: identifier, password }));
    saveTokens(tokens, remember);
    try {
      const profile = await request('/auth/profile/');
      return { profile, tokens };
    } catch (error) {
      clearTokens();
      throw error;
    }
  },
  async profile() {
    return request('/auth/profile/');
  },
  async logout() {
    const refresh = getRefreshToken();
    try {
      if (refresh) await request('/auth/logout/', json('POST', { refresh }), false);
    } finally {
      clearTokens();
    }
  },
  all(path) {
    return request(path).then(async (data) => {
      let results = Array.isArray(data) ? data : (data.results || []);
      let next = Array.isArray(data) ? null : data.next;
      while (next) {
        const page = await request(next);
        results = results.concat(page.results || []);
        next = page.next;
      }
      return results;
    });
  },
};

export function toFormData(values) {
  const data = new FormData();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') data.append(key, value);
  });
  return data;
}
