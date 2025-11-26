import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

const FileUpload = ({ onRemittanceUpload, onPdfUpload, onBatchUpload, loading }) => {
  const [remittanceFile, setRemittanceFile] = useState(null);
  const [pdfFile, setPdfFile] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);

  const onRemittanceDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setRemittanceFile(file);
      if (onRemittanceUpload) {
        onRemittanceUpload(file);
      }
    }
  }, [onRemittanceUpload]);

  const onPdfDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setPdfFile(file);
      if (onPdfUpload) {
        onPdfUpload(file);
      }
    }
  }, [onPdfUpload]);

  const remittanceDropzone = useDropzone({
    onDrop: onRemittanceDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: false,
    disabled: loading
  });

  const pdfDropzone = useDropzone({
    onDrop: onPdfDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: false,
    disabled: loading
  });

  const onBatchDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      setBatchFiles(acceptedFiles);
      if (onBatchUpload) {
        onBatchUpload(acceptedFiles);
      }
    }
  }, [onBatchUpload]);

  const batchDropzone = useDropzone({
    onDrop: onBatchDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: true,
    disabled: loading
  });

  const clearFiles = () => {
    setRemittanceFile(null);
    setPdfFile(null);
  };

  return (
    <div className="file-upload-container">
      <h2>Upload Documents</h2>
      
      <div className="upload-options">
        <div className="upload-section">
          <h3>Remittance PDF Only</h3>
          <div {...remittanceDropzone.getRootProps()} className={`dropzone ${remittanceDropzone.isDragActive ? 'active' : ''}`}>
            <input {...remittanceDropzone.getInputProps()} />
            {remittanceFile ? (
              <div className="file-info">
                <p>✓ {remittanceFile.name}</p>
                <button onClick={(e) => { e.stopPropagation(); setRemittanceFile(null); }}>Remove</button>
              </div>
            ) : (
              <p>Drag & drop a remittance PDF here, or click to select</p>
            )}
          </div>
        </div>

        <div className="upload-section">
          <h3>Lockbox Checks PDF</h3>
          <p className="upload-hint">Upload a lockbox PDF with multiple pages. Pages will be automatically grouped by check number. Check information and remittance details may be on different pages.</p>
          <div {...pdfDropzone.getRootProps()} className={`dropzone ${pdfDropzone.isDragActive ? 'active' : ''}`}>
            <input {...pdfDropzone.getInputProps()} />
            {pdfFile ? (
              <div className="file-info">
                <p>✓ {pdfFile.name}</p>
                <button onClick={(e) => { e.stopPropagation(); setPdfFile(null); }}>Remove</button>
              </div>
            ) : (
              <p>Drag & drop a PDF here, or click to select</p>
            )}
          </div>
        </div>

        <div className="upload-section">
          <h3>Batch Upload (Multiple Files)</h3>
          <p className="upload-hint">Upload multiple remittance PDFs to process separately</p>
          <div {...batchDropzone.getRootProps()} className={`dropzone ${batchDropzone.isDragActive ? 'active' : ''}`}>
            <input {...batchDropzone.getInputProps()} />
            {batchFiles.length > 0 ? (
              <div className="file-info">
                <p>✓ {batchFiles.length} file(s) selected:</p>
                <ul className="file-list">
                  {batchFiles.map((file, idx) => (
                    <li key={idx}>{file.name}</li>
                  ))}
                </ul>
                <button onClick={(e) => { e.stopPropagation(); setBatchFiles([]); }}>Clear All</button>
              </div>
            ) : (
              <p>Drag & drop multiple PDF files here, or click to select</p>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-indicator">
          <p>Processing files...</p>
          <p className="loading-hint">This may take 1-2 minutes for multi-page PDFs. Each page is being analyzed with AI vision processing.</p>
        </div>
      )}
    </div>
  );
};

export default FileUpload;

