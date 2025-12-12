import {z} from 'zod';

import {env} from '../env';

type ParamsObj = Record<string, string | number | undefined | (string | number)[]>;

function getCsrfToken(): string | null {
  const name = 'csrftoken';
  const cookieValue = document.cookie
    .split('; ')
    .find(row => row.startsWith(name + '='))
    ?.split('=')[1];
  return cookieValue || null;
}

export function paramsFromObject(params: ParamsObj): URLSearchParams {
  const urlParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value != null) {
      if (Array.isArray(value)) {
        value.forEach(v => urlParams.append(key, v.toString()));
      } else {
        urlParams.append(key, value.toString());
      }
    }
  });
  return urlParams;
}

interface FetchArgs<ResponseSchemaT extends z.ZodType> {
  path: string;
  query?: ParamsObj;
  body?: object;
  extraHeaders?: object;
  signal?: AbortSignal;
  responseSchema: ResponseSchemaT;
}

interface FetchArgsWithMethod<
  ResponseSchemaT extends z.ZodType,
> extends FetchArgs<ResponseSchemaT> {
  method: string;
}

async function _fetch<ResponseSchemaT extends z.ZodType>({
  path,
  query = {},
  method,
  body,
  extraHeaders = {},
  signal,
  responseSchema,
}: FetchArgsWithMethod<ResponseSchemaT>) {
  // Ensure path has trailing slash
  const normalizedPath = path.endsWith('/') ? path : path + '/';

  const queryString = paramsFromObject(query);
  const url = `${env.VITE_API_URL}${normalizedPath}${queryString ? '?' + queryString : ''}`;

  const headers: Record<string, string> = {
    ...extraHeaders,
  };

  // Add CSRF token for state-changing requests
  if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }
  }

  return fetch(url, {
    headers,
    method,
    signal,
    credentials: 'include',
    body: body ? JSON.stringify(body) : null,
  })
    .then(res => {
      if (!res.ok) {
        // might want to tweak this behavior. Might not be ideal to throw.
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      return res.json();
    })
    .then(data => {
      return responseSchema.parse(data);
    });
}

function get<ResponseSchemaT extends z.ZodType>({
  path,
  query = {},
  body = undefined,
  extraHeaders = {},
  signal,
  responseSchema,
}: FetchArgs<ResponseSchemaT>) {
  return _fetch({
    path,
    query,
    method: 'GET',
    body,
    extraHeaders,
    signal,
    responseSchema,
  });
}

function post<ResponseSchemaT extends z.ZodType>({
  path,
  query = {},
  body = undefined,
  extraHeaders = {},
  signal,
  responseSchema,
}: FetchArgs<ResponseSchemaT>) {
  return _fetch({
    path,
    query,
    method: 'POST',
    body,
    extraHeaders: {
      'Content-Type': 'application/json',
      ...extraHeaders,
    },
    signal,
    responseSchema,
  });
}

function patch<ResponseSchemaT extends z.ZodType>({
  path,
  query = {},
  body = undefined,
  extraHeaders = {},
  signal,
  responseSchema,
}: FetchArgs<ResponseSchemaT>) {
  return _fetch({
    path,
    query,
    method: 'PATCH',
    body,
    extraHeaders: {
      'Content-Type': 'application/json',
      ...extraHeaders,
    },
    signal,
    responseSchema,
  });
}

export const Api = {
  get,
  post,
  patch,
};
