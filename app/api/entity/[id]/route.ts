import { NextResponse } from 'next/server';

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://ffdrtpknppmtkkbqsvek.supabase.co';
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZmZHJ0cGtucHBtdGtrYnFzdmVrIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MTkxMzg3NiwiZXhwIjoyMDY3NDg5ODc2fQ.Vy6VzGOHWbTZNlRg_tZcyP3Y05LFf4g5sHYD6oaRY0s';

async function supabaseRequest(endpoint: string, params?: any) {
  const url = new URL(`${SUPABASE_URL}/rest/v1/${endpoint}`);
  
  if (params) {
    Object.keys(params).forEach(key => 
      url.searchParams.append(key, params[key])
    );
  }
  
  const response = await fetch(url.toString(), {
    headers: {
      'apikey': SUPABASE_KEY,
      'Authorization': `Bearer ${SUPABASE_KEY}`,
      'Content-Type': 'application/json'
    }
  });
  
  if (!response.ok) {
    throw new Error(`Supabase request failed: ${response.status}`);
  }
  
  return response.json();
}

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
    throw new Error(`RPC call failed: ${response.status}`);
  }
  
  return response.json();
}

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  try {
    const entityId = params.id;
    
    // Fetch entity info
    const entities = await supabaseRequest('entities', {
      'entity_id': `eq.${entityId}`,
      'select': '*',
      'limit': '1'
    });
    
    if (!entities || entities.length === 0) {
      return NextResponse.json({ error: 'Entity not found' }, { status: 404 });
    }
    
    const entity = entities[0];
    
    // Fetch primary record if exists
    let primaryRecord = null;
    if (entity.primary_record_id) {
      const records = await supabaseRequest('financial_records', {
        'record_id': `eq.${entity.primary_record_id}`,
        'select': '*',
        'limit': '1'
      });
      primaryRecord = records?.[0] || null;
    }
    
    // Fetch financial summary from transactions directly
    let financialSummary = null;
    try {
      // Try the function first
      financialSummary = await supabaseRpc('get_entity_financial_summary', {
        p_entity_id: parseInt(entityId)
      });
    } catch (error) {
      // Fallback: calculate from transactions table directly
      const transactions = await supabaseRequest('cf_transactions', {
        'entity_id': `eq.${entityId}`,
        'select': 'amount,transaction_type_disposition_id,transaction_date'
      });
      
      if (transactions && transactions.length > 0) {
        const summary = {
          total_raised: 0,
          total_spent: 0,
          transaction_count: transactions.length,
          donation_count: 0,
          expense_count: 0,
          earliest_transaction: null as string | null,
          latest_transaction: null as string | null
        };
        
        transactions.forEach((tx: any) => {
          if (tx.transaction_type_disposition_id === 1) {
            summary.total_raised += parseFloat(tx.amount) || 0;
            summary.donation_count++;
          } else if (tx.transaction_type_disposition_id === 2) {
            summary.total_spent += parseFloat(tx.amount) || 0;
            summary.expense_count++;
          }
          
          if (tx.transaction_date) {
            if (!summary.earliest_transaction || tx.transaction_date < summary.earliest_transaction) {
              summary.earliest_transaction = tx.transaction_date;
            }
            if (!summary.latest_transaction || tx.transaction_date > summary.latest_transaction) {
              summary.latest_transaction = tx.transaction_date;
            }
          }
        });
        
        financialSummary = [summary];
      }
    }
    
    // Fetch summary stats
    const stats = await supabaseRpc('get_entity_summary_stats', {
      p_entity_id: parseInt(entityId)
    });
    
    // Fetch reports
    const reports = await supabaseRpc('get_entity_reports_detailed', {
      p_entity_id: parseInt(entityId)
    });
    
    return NextResponse.json({
      entity,
      primaryRecord,
      financialSummary: financialSummary?.[0] || null,
      summaryStats: stats?.[0] || null,
      reports: reports || []
    });
  } catch (error) {
    console.error('API Error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch entity data' },
      { status: 500 }
    );
  }
}