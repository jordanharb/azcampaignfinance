import { NextResponse } from 'next/server';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://ffdrtpknppmtkkbqsvek.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s';

async function supabaseRpc(functionName: string, params: any) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/rpc/${functionName}`, {
    method: 'POST',
    headers: {
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(params)
  });
  
  if (!response.ok) {
    const error = await response.text();
    console.error('RPC Error:', error);
    throw new Error(`RPC call failed: ${response.status}`);
  }
  
  return response.json();
}

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const { searchParams } = new URL(request.url);
    const format = searchParams.get('format'); // 'csv' for download
    
    if (format === 'csv') {
      // Get all reports for CSV
      const data = await supabaseRpc('get_entity_reports_csv', {
        p_entity_id: parseInt(params.id)
      });
      return NextResponse.json(data);
    } else {
      // This is already fetched in the main entity endpoint
      // But we can provide it here too for consistency
      const data = await supabaseRpc('get_entity_reports_detailed', {
        p_entity_id: parseInt(params.id)
      });
      return NextResponse.json(data);
    }
  } catch (error) {
    console.error('Reports API Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch reports' },
      { status: 500 }
    );
  }
}