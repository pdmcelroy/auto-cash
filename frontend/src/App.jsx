import { useState } from 'react';
import FileUpload from './components/FileUpload';
import OCRResults from './components/OCRResults';
import InvoiceSuggestions from './components/InvoiceSuggestions';
import ReviewPanel from './components/ReviewPanel';
import { uploadCheck, uploadRemittance, uploadBoth } from './services/api';
import './App.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [matches, setMatches] = useState([]);
  const [selectedInvoice, setSelectedInvoice] = useState(null);
  const [error, setError] = useState(null);
  const [processingTime, setProcessingTime] = useState(null);

  const handleCheckUpload = async (file) => {
    setLoading(true);
    setError(null);
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoice(null);

    try {
      const response = await uploadCheck(file);
      setOcrResult(response.ocr_result);
      setMatches(response.matches);
      setProcessingTime(response.processing_time);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process check image');
      console.error('Error uploading check:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRemittanceUpload = async (file) => {
    setLoading(true);
    setError(null);
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoice(null);

    try {
      const response = await uploadRemittance(file);
      setOcrResult(response.ocr_result);
      setMatches(response.matches);
      setProcessingTime(response.processing_time);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process remittance PDF');
      console.error('Error uploading remittance:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBothUpload = async (checkFile, remittanceFile) => {
    if (!checkFile && !remittanceFile) {
      setError('Please upload at least one file');
      return;
    }

    setLoading(true);
    setError(null);
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoice(null);

    try {
      const response = await uploadBoth(checkFile, remittanceFile);
      setOcrResult(response.ocr_result);
      setMatches(response.matches);
      setProcessingTime(response.processing_time);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process files');
      console.error('Error uploading files:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectInvoice = (invoice) => {
    setSelectedInvoice(invoice);
  };

  const handleConfirm = () => {
    alert(`Invoice ${selectedInvoice.invoice_number} selected. Payment application feature coming soon!`);
    // TODO: Implement payment application in NetSuite
  };

  const handleCancel = () => {
    setSelectedInvoice(null);
  };

  const handleReset = () => {
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoice(null);
    setError(null);
    setProcessingTime(null);
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Cash Application System</h1>
        <p>Upload check images and remittances to find matching NetSuite invoices</p>
      </header>

      <main className="app-main">
        <FileUpload
          onCheckUpload={handleCheckUpload}
          onRemittanceUpload={handleRemittanceUpload}
          onBothUpload={handleBothUpload}
          loading={loading}
        />

        {error && (
          <div className="error-message">
            <strong>Error:</strong> {error}
          </div>
        )}

        {processingTime && (
          <div className="processing-info">
            Processed in {processingTime.toFixed(2)} seconds
          </div>
        )}

        {ocrResult && (
          <div className="results-section">
            <OCRResults ocrResult={ocrResult} />
            
            <InvoiceSuggestions
              matches={matches}
              onSelectInvoice={handleSelectInvoice}
              selectedInvoiceId={selectedInvoice?.invoice_id}
            />

            {selectedInvoice && (
              <ReviewPanel
                selectedInvoice={selectedInvoice}
                onConfirm={handleConfirm}
                onCancel={handleCancel}
              />
            )}

            <button onClick={handleReset} className="reset-btn">
              Process New Files
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
