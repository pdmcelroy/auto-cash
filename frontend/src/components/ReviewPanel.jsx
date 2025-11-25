const ReviewPanel = ({ selectedInvoices, onConfirm, onCancel }) => {
  if (!selectedInvoices || selectedInvoices.length === 0) {
    return null;
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleDateString();
    } catch {
      return dateString;
    }
  };

  const totalAmount = selectedInvoices.reduce((sum, inv) => sum + (inv.amount || 0), 0);

  return (
    <div className="review-panel">
      <h3>Review & Confirm</h3>
      
      <div className="review-content">
        <div className="selected-invoices">
          <h4>Selected Invoice{selectedInvoices.length > 1 ? 's' : ''} ({selectedInvoices.length})</h4>
          <div className="invoices-list">
            {selectedInvoices.map((invoice, idx) => (
              <div key={invoice.invoice_id} className="invoice-details">
                <div className="invoice-header">
                  <strong>Invoice #{idx + 1}: {invoice.invoice_number}</strong>
                  <span className="match-score-badge">Score: {invoice.match_score.toFixed(1)}</span>
                </div>
                <div className="detail-row">
                  <label>Customer:</label>
                  <span>{invoice.customer_name}</span>
                </div>
                <div className="detail-row">
                  <label>Amount:</label>
                  <span>${invoice.amount?.toFixed(2) || 'N/A'}</span>
                </div>
                {invoice.due_date && (
                  <div className="detail-row">
                    <label>Due Date:</label>
                    <span>{formatDate(invoice.due_date)}</span>
                  </div>
                )}
                {invoice.subsidiary && (
                  <div className="detail-row">
                    <label>Subsidiary:</label>
                    <span>{invoice.subsidiary}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
          <div className="total-amount">
            <strong>Total Amount: ${totalAmount.toFixed(2)}</strong>
          </div>
        </div>

        <div className="review-actions">
          <button onClick={onConfirm} className="confirm-btn">
            Confirm Match
          </button>
          <button onClick={onCancel} className="cancel-btn">
            Cancel
          </button>
        </div>

        <div className="review-note">
          <p><strong>Note:</strong> Payment application to NetSuite is not yet implemented. This is a read-only review interface.</p>
        </div>
      </div>
    </div>
  );
};

export default ReviewPanel;

