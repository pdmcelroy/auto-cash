const ReviewPanel = ({ selectedInvoice, onConfirm, onCancel }) => {
  if (!selectedInvoice) {
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

  return (
    <div className="review-panel">
      <h3>Review & Confirm</h3>
      
      <div className="review-content">
        <div className="selected-invoice">
          <h4>Selected Invoice</h4>
          <div className="invoice-details">
            <div className="detail-row">
              <label>Invoice Number:</label>
              <span>{selectedInvoice.invoice_number}</span>
            </div>
            <div className="detail-row">
              <label>Customer:</label>
              <span>{selectedInvoice.customer_name}</span>
            </div>
            <div className="detail-row">
              <label>Amount:</label>
              <span>${selectedInvoice.amount?.toFixed(2) || 'N/A'}</span>
            </div>
            {selectedInvoice.due_date && (
              <div className="detail-row">
                <label>Due Date:</label>
                <span>{formatDate(selectedInvoice.due_date)}</span>
              </div>
            )}
            {selectedInvoice.subsidiary && (
              <div className="detail-row">
                <label>Subsidiary:</label>
                <span>{selectedInvoice.subsidiary}</span>
              </div>
            )}
            <div className="detail-row">
              <label>Match Score:</label>
              <span>{selectedInvoice.match_score.toFixed(1)}</span>
            </div>
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

