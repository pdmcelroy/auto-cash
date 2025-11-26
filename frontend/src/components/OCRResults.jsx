const OCRResults = ({ ocrResult }) => {
  if (!ocrResult) {
    return null;
  }

  return (
    <div className="ocr-results">
      <h3>Extracted Data</h3>
      <div className="ocr-data-grid">
        {/* Always show these critical fields */}
        <div className="ocr-field">
          <label>Check Number:</label>
          <span>{ocrResult.check_number || <em>Not extracted</em>}</span>
        </div>
        
        <div className="ocr-field">
          <label>Amount:</label>
          <span>{ocrResult.amount ? `$${ocrResult.amount.toFixed(2)}` : <em>Not extracted</em>}</span>
        </div>
        
        <div className="ocr-field">
          <label>Date:</label>
          <span>{ocrResult.date || <em>Not extracted</em>}</span>
        </div>
        
        <div className="ocr-field">
          <label>Payor/Customer:</label>
          <span>{ocrResult.payor_name || ocrResult.customer_name || <em>Not extracted</em>}</span>
        </div>
        
        {ocrResult.payee_name && (
          <div className="ocr-field">
            <label>Payee:</label>
            <span>{ocrResult.payee_name}</span>
          </div>
        )}
        
        {ocrResult.customer_name && ocrResult.customer_name !== ocrResult.payor_name && (
          <div className="ocr-field">
            <label>Customer:</label>
            <span>{ocrResult.customer_name}</span>
          </div>
        )}
        
        {ocrResult.invoice_numbers && ocrResult.invoice_numbers.length > 0 && (
          <div className="ocr-field full-width">
            <label>Invoice Numbers Found:</label>
            <div className="invoice-numbers">
              {ocrResult.invoice_numbers.map((inv, idx) => (
                <span key={idx} className="invoice-badge">{inv}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {ocrResult.raw_text && (
        <details className="raw-text-section">
          <summary>View Raw Extracted Text</summary>
          <pre className="raw-text">{ocrResult.raw_text}</pre>
        </details>
      )}
    </div>
  );
};

export default OCRResults;


