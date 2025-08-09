// Server-side Supabase REST client
// WARNING: This file contains the service role key and should NEVER be imported client-side

const SUPABASE_URL = process.env.SUPABASE_URL!;
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY!;

if (!SUPABASE_URL || !SERVICE_ROLE_KEY) {
  throw new Error('Missing required environment variables: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY');
}

const REST_BASE = `${SUPABASE_URL}/rest/v1`;

/**
 * Generic REST API fetcher with service role authentication
 * Only use this on the server side - never expose to client
 */
export async function restJson<T = any>(
  path: string, 
  init: RequestInit = {}
): Promise<T> {
  const url = `${REST_BASE}/${path}`;
  
  const response = await fetch(url, {
    ...init,
    headers: {
      'apikey': SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json',
      ...(init.headers || {})
    },
    // Cache responses for 60 seconds to improve performance
    next: { revalidate: 60, ...init.next }
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    console.error(`REST API error: ${response.status} ${response.statusText}`, errorText);
    throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Call a Supabase RPC (stored procedure) function
 */
export async function callRpc<T = any>(
  functionName: string, 
  body: Record<string, any>
): Promise<T> {
  const url = `${REST_BASE}/rpc/${functionName}`;
  
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'apikey': SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body),
    next: { revalidate: 60 }
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    console.error(`RPC error: ${response.status} ${response.statusText}`, errorText);
    throw new Error(`RPC call failed: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Fetch CSV data from a REST endpoint
 * Returns raw response for streaming to client
 */
export async function restCsv(path: string): Promise<Response> {
  const url = `${REST_BASE}/${path}`;
  
  const response = await fetch(url, {
    headers: {
      'apikey': SERVICE_ROLE_KEY,
      'Authorization': `Bearer ${SERVICE_ROLE_KEY}`,
      'Accept': 'text/csv'
    }
  });
  
  if (!response.ok) {
    const errorText = await response.text();
    console.error(`CSV API error: ${response.status} ${response.statusText}`, errorText);
    throw new Error(`CSV request failed: ${response.status} ${response.statusText}`);
  }
  
  return response;
}