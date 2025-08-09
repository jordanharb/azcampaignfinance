import { restJson } from '@/lib/rest';
import { Entity, EntityRecord, Report, Transaction } from '@/lib/types';
import { APP_CONFIG } from '@/lib/constants';
import { notFound } from 'next/navigation';

interface CandidatePageProps {
  params: { id: string };
}

async function loadEntityData(entityId: string) {
  try {
    // Load entity details
    const entities = await restJson<Entity[]>(`cf_entities?entity_id=eq.${entityId}&select=*`);
    const entity = entities[0];
    
    if (!entity) {
      return null;
    }

    // Load primary entity record
    const records = await restJson<EntityRecord[]>(
      `cf_entity_records?entity_id=eq.${entityId}&select=party_name,office_name,is_primary_record,registration_date&order=is_primary_record.desc,registration_date.desc&limit=1`
    );
    const primaryRecord = records[0] || null;

    // Load reports
    const reports = await restJson<Report[]>(
      `vw_reports_export?entity_id=eq.${entityId}&select=*&order=rpt_file_date.desc`
    );

    // Load transaction preview (limited)
    const transactions = await restJson<Transaction[]>(
      `vw_transactions_export?entity_id=eq.${entityId}&select=*&order=transaction_date.desc&limit=${APP_CONFIG.TRANSACTION_PREVIEW_LIMIT}`
    );

    return {
      entity,
      primaryRecord,
      reports,
      transactions,
    };
  } catch (error) {
    console.error('Error loading entity data:', error);
    return null;
  }
}

function formatCurrency(amount: number | null | undefined): string {
  if (!amount || amount === 0) return '$0';
  return `$${Math.round(amount).toLocaleString()}`;
}

function formatDate(dateString: string | null): string {
  if (!dateString) return '—';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  } catch {
    return '—';
  }
}

export default async function CandidatePage({ params }: CandidatePageProps) {
  const data = await loadEntityData(params.id);
  
  if (!data) {
    notFound();
  }

  const { entity, primaryRecord, reports, transactions } = data;
  const entityName = entity.primary_candidate_name || entity.primary_committee_name || 'Unknown Entity';

  return (
    <div>
      {/* Header Section */}
      <div style={{
        marginBottom: '2rem',
        padding: '2rem',
        backgroundColor: '#f8f9fa',
        borderRadius: '0.5rem',
        border: '1px solid #e5e5e5',>
        <h1 style={{
          fontSize: '2rem',
          fontWeight: '700',
          marginBottom: '1rem',
          color: '#1f2937',
          lineHeight: '1.2',>
          {entityName}
        </h1>
        
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1.5rem',
          alignItems: 'center',
          marginBottom: '2rem',
          fontSize: '0.95rem',
          color: '#6b7280',>
          <span>
            <strong>Party:</strong> {primaryRecord?.party_name || '—'}
          </span>
          <span>
            <strong>Office:</strong> {primaryRecord?.office_name || '—'}
          </span>
          <span>
            <strong>Last Activity:</strong> {formatDate(entity.latest_activity)}
          </span>
        </div>

        {/* Financial Summary */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '2rem',>
          <div style={{
            padding: '1rem',
            backgroundColor: 'white',
            borderRadius: '0.375rem',
            border: '1px solid #e5e7eb',>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'>
              Total Income
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#16a34a'>
              {formatCurrency(entity.total_income_all_records)}
            </div>
          </div>
          <div style={{
            padding: '1rem',
            backgroundColor: 'white',
            borderRadius: '0.375rem',
            border: '1px solid #e5e7eb',>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'>
              Total Expense
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#dc2626'>
              {formatCurrency(entity.total_expense_all_records)}
            </div>
          </div>
          <div style={{
            padding: '1rem',
            backgroundColor: 'white',
            borderRadius: '0.375rem',
            border: '1px solid #e5e7eb',>
            <div style={{ fontSize: '0.8rem', color: '#6b7280', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em'>
              Reports
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#0066cc'>
              {reports.length}
            </div>
          </div>
        </div>

        {/* Download Buttons */}
        <div style={{
          display: 'flex',
          gap: '1rem',
          flexWrap: 'wrap',>
          <form action={`/api/download/entity-reports`} method="get">
            <input type="hidden" name="id" value={params.id} />
            <button 
              type="submit"
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '0.95rem',
                fontWeight: '600',
                color: 'white',
                backgroundColor: '#16a34a',
                border: 'none',
                borderRadius: '0.5rem',
                cursor: 'pointer',
                transition: 'background-color 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
            >
              📄 Download All Reports (CSV)
            </button>
          </form>
          
          <form action={`/api/download/entity-transactions`} method="get">
            <input type="hidden" name="id" value={params.id} />
            <button 
              type="submit"
              style={{
                padding: '0.75rem 1.5rem',
                fontSize: '0.95rem',
                fontWeight: '600',
                color: 'white',
                backgroundColor: '#0066cc',
                border: 'none',
                borderRadius: '0.5rem',
                cursor: 'pointer',
                transition: 'background-color 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
            >
              💰 Download All Transactions (CSV)
            </button>
          </form>
        </div>
      </div>

      {/* Reports Section */}
      <section style={{ marginBottom: '3rem'>
        <h2 style={{
          fontSize: '1.5rem',
          fontWeight: '700',
          marginBottom: '1rem',
          color: '#1f2937',>
          Reports ({reports.length})
        </h2>
        
        {reports.length > 0 ? (
          <div style={{
            border: '1px solid #e5e5e5',
            borderRadius: '0.5rem',
            overflow: 'hidden',
            backgroundColor: 'white',>
            <div style={{ overflowX: 'auto'>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.9rem',>
                <thead>
                  <tr style={{
                    backgroundColor: '#f9fafb',
                    borderBottom: '1px solid #e5e5e5',>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '100px'>Date</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '200px'>Report</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontWeight: '600', minWidth: '120px'>Donations</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontWeight: '600', minWidth: '120px'>Expenditures</th>
                    <th style={{ padding: '0.75rem', textAlign: 'center', fontWeight: '600', minWidth: '80px'>PDF</th>
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <tr 
                      key={report.report_id}
                      style={{
                        borderBottom: '1px solid #f0f0f0',
                        transition: 'background-color 0.15s ease',
                    >
                      <td style={{ padding: '0.75rem', color: '#4b5563'>
                        {formatDate(report.rpt_file_date)}
                      </td>
                      <td style={{ padding: '0.75rem', fontWeight: '500'>
                        {report.rpt_title || report.rpt_name || '—'}
                      </td>
                      <td style={{ 
                        padding: '0.75rem', 
                        textAlign: 'right',
                        fontFamily: 'ui-monospace, Monaco, Consolas, monospace',
                        fontSize: '0.85rem',
                        color: '#16a34a',>
                        {formatCurrency(report.total_donations)}
                      </td>
                      <td style={{ 
                        padding: '0.75rem', 
                        textAlign: 'right',
                        fontFamily: 'ui-monospace, Monaco, Consolas, monospace',
                        fontSize: '0.85rem',
                        color: '#dc2626',>
                        {formatCurrency(report.total_expenditures)}
                      </td>
                      <td style={{ padding: '0.75rem', textAlign: 'center'>
                        {report.pdf_url ? (
                          <a 
                            href={report.pdf_url} 
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                              color: '#0066cc',
                              textDecoration: 'none',
                              fontSize: '0.85rem',
                              fontWeight: '500',
                          >
                            View PDF
                          </a>
                        ) : (
                          <span style={{ color: '#9ca3af'>—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div style={{
            padding: '2rem',
            textAlign: 'center',
            backgroundColor: '#f9fafb',
            border: '1px solid #e5e5e5',
            borderRadius: '0.5rem',
            color: '#6b7280',>
            No reports available for this entity.
          </div>
        )}
      </section>

      {/* Transactions Preview Section */}
      <section>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '1rem',>
          <h2 style={{
            fontSize: '1.5rem',
            fontWeight: '700',
            color: '#1f2937',
            margin: 0,>
            Recent Transactions
          </h2>
          <div style={{
            fontSize: '0.85rem',
            color: '#6b7280',
            fontStyle: 'italic',>
            Showing {Math.min(transactions.length, APP_CONFIG.TRANSACTION_PREVIEW_LIMIT)} most recent
          </div>
        </div>
        
        {transactions.length > 0 ? (
          <div style={{
            border: '1px solid #e5e5e5',
            borderRadius: '0.5rem',
            overflow: 'hidden',
            backgroundColor: 'white',>
            <div style={{ overflowX: 'auto'>
              <table style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: '0.9rem',>
                <thead>
                  <tr style={{
                    backgroundColor: '#f9fafb',
                    borderBottom: '1px solid #e5e5e5',>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '100px'>Date</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '150px'>Type</th>
                    <th style={{ padding: '0.75rem', textAlign: 'right', fontWeight: '600', minWidth: '100px'>Amount</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '200px'>Counterparty</th>
                    <th style={{ padding: '0.75rem', textAlign: 'left', fontWeight: '600', minWidth: '120px'>Location</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((transaction) => (
                    <tr 
                      key={transaction.public_transaction_id}
                      style={{
                        borderBottom: '1px solid #f0f0f0',
                        transition: 'background-color 0.15s ease',
                    >
                      <td style={{ padding: '0.75rem', color: '#4b5563'>
                        {formatDate(transaction.transaction_date)}
                      </td>
                      <td style={{ padding: '0.75rem', fontSize: '0.85rem'>
                        {transaction.transaction_type || '—'}
                      </td>
                      <td style={{ 
                        padding: '0.75rem', 
                        textAlign: 'right',
                        fontFamily: 'ui-monospace, Monaco, Consolas, monospace',
                        fontSize: '0.85rem',
                        fontWeight: '600',>
                        {formatCurrency(transaction.amount)}
                      </td>
                      <td style={{ 
                        padding: '0.75rem',
                        fontSize: '0.85rem',
                        maxWidth: '200px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',>
                        {transaction.counterparty_name || transaction.received_from_or_paid_to || '—'}
                      </td>
                      <td style={{ 
                        padding: '0.75rem',
                        color: '#6b7280',
                        fontSize: '0.85rem',>
                        {[transaction.transaction_city, transaction.transaction_state].filter(Boolean).join(', ') || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div style={{
            padding: '2rem',
            textAlign: 'center',
            backgroundColor: '#f9fafb',
            border: '1px solid #e5e5e5',
            borderRadius: '0.5rem',
            color: '#6b7280',>
            No transactions available for this entity.
          </div>
        )}

        {transactions.length >= APP_CONFIG.TRANSACTION_PREVIEW_LIMIT && (
          <div style={{
            marginTop: '1rem',
            padding: '1rem',
            backgroundColor: '#eff6ff',
            border: '1px solid #bfdbfe',
            borderRadius: '0.375rem',
            fontSize: '0.9rem',
            color: '#1e40af',>
            <strong>Note:</strong> This shows only the {APP_CONFIG.TRANSACTION_PREVIEW_LIMIT} most recent transactions. 
            Use the "Download All Transactions (CSV)" button above to get the complete dataset.
          </div>
        )}
      </section>
    </div>
  );
}