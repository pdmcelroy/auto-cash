const InvoiceSuggestions = ({ matches, onSelectInvoice, selectedInvoiceIds = [] }) => {
  if (!matches || matches.length === 0) {
    return (
      <div className="invoice-suggestions">
        <h3>Invoice Matches</h3>
        <p className="no-matches">No matching invoices found with score above 100.</p>
      </div>
    );
  }

  const getScoreColor = (score) => {
    if (score >= 200) return 'high-score';
    if (score >= 150) return 'medium-score';
    return 'low-score';
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  const handleToggleInvoice = (invoice) => {
    if (onSelectInvoice) {
      onSelectInvoice(invoice);
    }
  };

  const isSelected = (invoiceId) => {
    return selectedInvoiceIds.includes(invoiceId);
  };

  return (
    <div className="invoice-suggestions">
      <h3>Invoice Matches ({matches.length})</h3>
      <p className="matches-description">Select one or more invoices that match this payment:</p>
      
      <div className="matches-list">
        {matches.map((match) => (
          <div
            key={match.invoice_id}
            className={`invoice-match ${isSelected(match.invoice_id) ? 'selected' : ''} ${getScoreColor(match.match_score)}`}
          >
            <div className="invoice-checkbox">
              <input
                type="checkbox"
                checked={isSelected(match.invoice_id)}
                onChange={() => handleToggleInvoice(match)}
                onClick={(e) => e.stopPropagation()}
              />
            </div>
            <div 
              className="invoice-match-content"
              onClick={() => handleToggleInvoice(match)}
            >
            <div className="match-header">
              <div className="match-score">
                <span className="score-value">{match.match_score.toFixed(1)}</span>
                <span className="score-label">Match Score</span>
              </div>
              <div className="match-info">
                <h4>Invoice #{match.invoice_number}</h4>
                <p className="customer-name">{match.customer_name}</p>
              </div>
            </div>
            
            <div className="match-details">
              <div className="detail-item">
                <label>Amount:</label>
                <span>${match.amount?.toFixed(2) || 'N/A'}</span>
              </div>
              {match.due_date && (
                <div className="detail-item">
                  <label>Due Date:</label>
                  <span>{formatDate(match.due_date)}</span>
                </div>
              )}
              {match.subsidiary && (
                <div className="detail-item">
                  <label>Subsidiary:</label>
                  <span>{match.subsidiary}</span>
                </div>
              )}
            </div>
            
            {match.match_reasons && match.match_reasons.length > 0 && (
              <div className="match-reasons">
                <strong>Match Reasons:</strong>
                <ul>
                  {match.match_reasons.map((reason, idx) => (
                    <li key={idx}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default InvoiceSuggestions;

