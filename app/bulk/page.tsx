'use client';

import { useState } from 'react';
import { BulkExportRequest, ExportJob } from '@/lib/types';
import { APP_CONFIG, ERROR_MESSAGES } from '@/lib/constants';

export default function BulkExportPage() {
  const [entityIds, setEntityIds] = useState('');
  const [exportKind, setExportKind] = useState<'reports' | 'transactions'>('transactions');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExportJob | null>(null);
  const [error, setError] = useState<string | null>(null);

  function parseEntityIds(input: string): number[] {
    return input
      .split(/[\s,]+/)
      .map(s => s.trim())
      .filter(Boolean)
      .map(s => parseInt(s, 10))
      .filter(n => !isNaN(n) && n > 0);
  }

  function validateForm(): string | null {
    const ids = parseEntityIds(entityIds);
    
    if (ids.length === 0) {
      return 'Please enter at least one valid entity ID';
    }
    
    if (ids.length > APP_CONFIG.MAX_ENTITY_IDS) {
      return `Too many entity IDs. Maximum allowed: ${APP_CONFIG.MAX_ENTITY_IDS}`;
    }

    // Validate date range if provided
    if (dateFrom && dateTo && new Date(dateFrom) > new Date(dateTo)) {
      return 'From date cannot be after To date';
    }

    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const ids = parseEntityIds(entityIds);
      const filters: BulkExportRequest['filters'] = {};
      
      if (dateFrom) filters.date_from = dateFrom;
      if (dateTo) filters.date_to = dateTo;

      const payload: BulkExportRequest = {
        kind: exportKind,
        entity_ids: ids,
        filters,
      };

      const response = await fetch('/api/bulk-export', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Export failed');
      }

      setResult(data);
    } catch (err) {
      console.error('Bulk export error:', err);
      setError(err instanceof Error ? err.message : ERROR_MESSAGES.EXPORT_FAILED);
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setEntityIds('');
    setDateFrom('');
    setDateTo('');
    setResult(null);
    setError(null);
  }

  return (
    <div>
      <div style={{ marginBottom: '2rem'>
        <h1 style={{
          fontSize: '2rem',
          fontWeight: '700',
          marginBottom: '0.5rem',
          color: '#1f2937',>
          Bulk Export
        </h1>
        <p style={{
          fontSize: '1rem',
          color: '#6b7280',
          marginBottom: '0',
          maxWidth: '600px',>
          Export data for multiple entities at once. The system will generate a CSV file and provide a download link.
        </p>
      </div>

      <div style={{
        maxWidth: '700px',
        backgroundColor: '#f9fafb',
        padding: '2rem',
        borderRadius: '0.5rem',
        border: '1px solid #e5e7eb',>
        <form onSubmit={handleSubmit}>
          {/* Entity IDs Input */}
          <div style={{ marginBottom: '1.5rem'>
            <label 
              htmlFor="entityIds"
              style={{
                display: 'block',
                fontSize: '0.9rem',
                fontWeight: '600',
                color: '#374151',
                marginBottom: '0.5rem',
            >
              Entity IDs <span style={{ color: '#dc2626'>*</span>
            </label>
            <textarea
              id="entityIds"
              value={entityIds}
              onChange={(e) => setEntityIds(e.target.value)}
              rows={4}
              placeholder="Enter entity IDs separated by commas or spaces. Example: 101502, 101817, 101475"
              style={{
                width: '100%',
                padding: '0.75rem',
                fontSize: '0.9rem',
                border: '2px solid #d1d5db',
                borderRadius: '0.375rem',
                outline: 'none',
                resize: 'vertical',
                fontFamily: 'ui-monospace, Monaco, Consolas, monospace',
            />
            <div style={{
              fontSize: '0.8rem',
              color: '#6b7280',
              marginTop: '0.25rem',>
              Maximum {APP_CONFIG.MAX_ENTITY_IDS} entity IDs per export
            </div>
          </div>

          {/* Export Type */}
          <div style={{ marginBottom: '1.5rem'>
            <label 
              htmlFor="exportKind"
              style={{
                display: 'block',
                fontSize: '0.9rem',
                fontWeight: '600',
                color: '#374151',
                marginBottom: '0.5rem',
            >
              Export Type
            </label>
            <select
              id="exportKind"
              value={exportKind}
              onChange={(e) => setExportKind(e.target.value as 'reports' | 'transactions')}
              style={{
                width: '100%',
                padding: '0.75rem',
                fontSize: '0.9rem',
                border: '2px solid #d1d5db',
                borderRadius: '0.375rem',
                outline: 'none',
                backgroundColor: 'white',
            >
              <option value="transactions">Transactions</option>
              <option value="reports">Reports</option>
            </select>
          </div>

          {/* Date Range */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '1rem',
            marginBottom: '1.5rem',>
            <div>
              <label 
                htmlFor="dateFrom"
                style={{
                  display: 'block',
                  fontSize: '0.9rem',
                  fontWeight: '600',
                  color: '#374151',
                  marginBottom: '0.5rem',
              >
                From Date (Optional)
              </label>
              <input
                id="dateFrom"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  fontSize: '0.9rem',
                  border: '2px solid #d1d5db',
                  borderRadius: '0.375rem',
                  outline: 'none',
              />
            </div>
            
            <div>
              <label 
                htmlFor="dateTo"
                style={{
                  display: 'block',
                  fontSize: '0.9rem',
                  fontWeight: '600',
                  color: '#374151',
                  marginBottom: '0.5rem',
              >
                To Date (Optional)
              </label>
              <input
                id="dateTo"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem',
                  fontSize: '0.9rem',
                  border: '2px solid #d1d5db',
                  borderRadius: '0.375rem',
                  outline: 'none',
              />
            </div>
          </div>

          {/* Action Buttons */}
          <div style={{
            display: 'flex',
            gap: '1rem',
            alignItems: 'center',>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '0.75rem 2rem',
                fontSize: '1rem',
                fontWeight: '600',
                color: 'white',
                backgroundColor: loading ? '#9ca3af' : '#0066cc',
                border: 'none',
                borderRadius: '0.5rem',
                cursor: loading ? 'not-allowed' : 'pointer',
                transition: 'background-color 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                if (!loading) {
                  e.currentTarget.style.backgroundColor = '#0052a3';
                }
                if (!loading) {
                  e.currentTarget.style.backgroundColor = '#0066cc';
                }
            >
              {loading ? (
                <>
                  <span style={{
                    display: 'inline-block',
                    width: '1rem',
                    height: '1rem',
                    border: '2px solid transparent',
                    borderTop: '2px solid currentColor',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite', />
                  Preparing Export...
                </>
              ) : (
                <>
                  📊 Prepare Export
                </>
              )}
            </button>

            {(result || error) && (
              <button
                type="button"
                onClick={handleReset}
                style={{
                  padding: '0.75rem 1.5rem',
                  fontSize: '0.9rem',
                  fontWeight: '500',
                  color: '#6b7280',
                  backgroundColor: 'transparent',
                  border: '1px solid #d1d5db',
                  borderRadius: '0.375rem',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
              >
                Reset Form
              </button>
            )}
          </div>
        </form>

        {/* Results */}
        {result && (
          <div style={{
            marginTop: '2rem',
            padding: '1.5rem',
            backgroundColor: '#f0f9ff',
            border: '2px solid #0ea5e9',
            borderRadius: '0.5rem',>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '1rem',>
              <span style={{ fontSize: '1.25rem'>✅</span>
              <h3 style={{
                fontSize: '1.1rem',
                fontWeight: '600',
                color: '#0c4a6e',
                margin: 0,>
                Export Ready!
              </h3>
            </div>
            <p style={{
              color: '#155e75',
              marginBottom: '1rem',
              fontSize: '0.9rem',>
              Your {exportKind} export has been generated successfully.
            </p>
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1.5rem',
                fontSize: '0.95rem',
                fontWeight: '600',
                color: 'white',
                backgroundColor: '#16a34a',
                textDecoration: 'none',
                borderRadius: '0.5rem',
                transition: 'background-color 0.2s ease',
            >
              📥 Download CSV File
            </a>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            marginTop: '2rem',
            padding: '1.5rem',
            backgroundColor: '#fef2f2',
            border: '2px solid #f87171',
            borderRadius: '0.5rem',>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '0.5rem',>
              <span style={{ fontSize: '1.25rem'>❌</span>
              <h3 style={{
                fontSize: '1.1rem',
                fontWeight: '600',
                color: '#991b1b',
                margin: 0,>
                Export Failed
              </h3>
            </div>
            <p style={{
              color: '#b91c1c',
              margin: 0,
              fontSize: '0.9rem',>
              {error}
            </p>
          </div>
        )}
      </div>

      {/* Help Section */}
      <div style={{
        marginTop: '3rem',
        padding: '2rem',
        backgroundColor: '#fffbeb',
        border: '1px solid #fed7aa',
        borderRadius: '0.5rem',>
        <h3 style={{
          fontSize: '1.1rem',
          fontWeight: '600',
          color: '#92400e',
          marginBottom: '1rem',>
          How to use bulk export
        </h3>
        <ul style={{
          color: '#a16207',
          fontSize: '0.9rem',
          margin: 0,
          paddingLeft: '1.5rem',
          lineHeight: '1.6',>
          <li style={{ marginBottom: '0.5rem'>
            <strong>Entity IDs:</strong> You can find entity IDs in the search results or candidate pages
          </li>
          <li style={{ marginBottom: '0.5rem'>
            <strong>Export Types:</strong> Choose "Reports" for filing documents or "Transactions" for detailed financial activity
          </li>
          <li style={{ marginBottom: '0.5rem'>
            <strong>Date Filters:</strong> Optional - limit results to a specific time period
          </li>
          <li>
            <strong>File Format:</strong> All exports are provided as CSV files for easy analysis in spreadsheet applications
          </li>
        </ul>
      </div>

      {/* Inline styles for spinner animation */}
      <style jsx>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}