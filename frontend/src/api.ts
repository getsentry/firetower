import {z} from 'zod';

import {env} from '../env';

type ParamsObj = Record<string, string | number | undefined>;

export function paramsFromObject(params: ParamsObj): URLSearchParams {
  const urlParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value != null) {
      urlParams.append(key, value.toString());
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

interface FetchArgsWithMethod<ResponseSchemaT extends z.ZodType>
  extends FetchArgs<ResponseSchemaT> {
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

  return fetch(url, {
    headers: {
      ...extraHeaders,
    },
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
    extraHeaders,
    signal,
    responseSchema,
  });
}

export const Api = {
  get,
  post,
  // add other methods as needed
};
