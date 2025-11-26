import { useState } from 'react';
import FileUpload from './components/FileUpload';
import OCRResults from './components/OCRResults';
import InvoiceSuggestions from './components/InvoiceSuggestions';
import ReviewPanel from './components/ReviewPanel';
import { uploadRemittance, uploadPdf, uploadBatch } from './services/api';
import './App.css';

function App() {
  const [loading, setLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [matches, setMatches] = useState([]);
  const [selectedInvoices, setSelectedInvoices] = useState([]);
  const [error, setError] = useState(null);
  const [processingTime, setProcessingTime] = useState(null);
  const [batchResults, setBatchResults] = useState([]); // Array of {checkNumber, ocrResult, matches}

  const handleRemittanceUpload = async (file) => {
    setLoading(true);
    setError(null);
      setOcrResult(null);
      setMatches([]);
      setSelectedInvoices([]);

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

  const handlePdfUpload = async (file) => {
    setLoading(true);
    setError(null);
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoices([]);
    setBatchResults([]);

    try {
      const response = await uploadPdf(file);
      
      // Convert PDF response to batch results format for consistent display
      const processedResults = response.check_groups.map((group, idx) => {
        const checkNumber = group.check_number || `Check ${idx + 1}`;
        
        return {
          id: group.check_number || `check-${idx}`,
          checkNumber: checkNumber,
          ocrResult: group.ocr_result,
          matches: group.matches,
          processingTime: group.processing_time,
          pages: group.pages,
          filename: file.name
        };
      });
      
      setBatchResults(processedResults);
      setProcessingTime(response.total_processing_time);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process PDF');
      console.error('Error uploading PDF:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchUpload = async (files) => {
    if (!files || files.length === 0) {
      setError('Please upload at least one file');
      return;
    }

    setLoading(true);
    setError(null);
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoices([]);
    setBatchResults([]);

    try {
      const response = await uploadBatch(files);
      
      // Process batch results - group by check number
      const processedResults = response.results.map((result, idx) => {
        const filename = files[idx]?.name || `File ${idx + 1}`;
        // Use filename (without extension) as fallback if check number not extracted
        const filenameBase = filename.replace(/\.[^/.]+$/, ''); // Remove extension
        const checkNumber = result.ocr_result.check_number || filenameBase;
        
        return {
          id: result.ocr_result.check_number || `file-${idx}`,
          checkNumber: checkNumber,
          ocrResult: result.ocr_result,
          matches: result.matches,
          processingTime: result.processing_time,
          filename: filename
        };
      });
      
      setBatchResults(processedResults);
      setProcessingTime(response.total_processing_time);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to process batch files');
      console.error('Error uploading batch:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectInvoice = (invoice) => {
    setSelectedInvoices(prev => {
      // For batch uploads, include check number in comparison to allow same invoice for different checks
      const invoiceKey = invoice.checkNumber 
        ? `${invoice.invoice_id}_${invoice.checkNumber}`
        : invoice.invoice_id;
      
      const isSelected = prev.some(inv => {
        const invKey = inv.checkNumber 
          ? `${inv.invoice_id}_${inv.checkNumber}`
          : inv.invoice_id;
        return invKey === invoiceKey;
      });
      
      if (isSelected) {
        // Remove if already selected
        return prev.filter(inv => {
          const invKey = inv.checkNumber 
            ? `${inv.invoice_id}_${inv.checkNumber}`
            : inv.invoice_id;
          return invKey !== invoiceKey;
        });
      } else {
        // Add if not selected
        return [...prev, invoice];
      }
    });
  };

  const handleConfirm = () => {
    if (selectedInvoices.length === 0) {
      alert('Please select at least one invoice');
      return;
    }
    const invoiceNumbers = selectedInvoices.map(inv => inv.invoice_number).join(', ');
    alert(`Selected ${selectedInvoices.length} invoice(s): ${invoiceNumbers}. Payment application feature coming soon!`);
    // TODO: Implement payment application in NetSuite
  };

  const handleCancel = () => {
    setSelectedInvoices([]);
  };

  const handleReset = () => {
    setOcrResult(null);
    setMatches([]);
    setSelectedInvoices([]);
    setBatchResults([]);
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
          onRemittanceUpload={handleRemittanceUpload}
          onPdfUpload={handlePdfUpload}
          onBatchUpload={handleBatchUpload}
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

        {/* Single file results */}
        {ocrResult && !batchResults.length && (
          <div className="results-section">
            <OCRResults ocrResult={ocrResult} />
            
            <InvoiceSuggestions
              matches={matches}
              onSelectInvoice={handleSelectInvoice}
              selectedInvoiceIds={selectedInvoices.map(inv => inv.invoice_id)}
            />

            {selectedInvoices.length > 0 && (
              <ReviewPanel
                selectedInvoices={selectedInvoices}
                onConfirm={handleConfirm}
                onCancel={handleCancel}
              />
            )}

            <button onClick={handleReset} className="reset-btn">
              Process New Files
            </button>
          </div>
        )}

        {/* Batch results */}
        {batchResults.length > 0 && (
          <div className="batch-results-section">
            <h2>Batch Processing Results ({batchResults.length} file(s))</h2>
            {batchResults.map((result, idx) => (
              <div key={result.id} className="batch-result-item">
                <div className="batch-result-header">
                  <h3>
                    {result.ocrResult.check_number 
                      ? `Check #${result.checkNumber}` 
                      : `Check: ${result.filename}`}
                    {result.ocrResult.check_number && ` - ${result.filename}`}
                    {result.pages && result.pages.length > 0 && (
                      <span className="page-info"> (Pages {result.pages.map(p => p + 1).join(', ')})</span>
                    )}
                  </h3>
                  <span className="processing-time">Processed in {result.processingTime.toFixed(2)}s</span>
                </div>
                <OCRResults ocrResult={result.ocrResult} />
                <InvoiceSuggestions
                  matches={result.matches}
                  onSelectInvoice={(invoice) => {
                    // Add check number context to invoice selection
                    handleSelectInvoice({...invoice, checkNumber: result.checkNumber});
                  }}
                  selectedInvoiceIds={selectedInvoices
                    .filter(inv => inv.checkNumber === result.checkNumber)
                    .map(inv => inv.invoice_id)}
                />
              </div>
            ))}
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
