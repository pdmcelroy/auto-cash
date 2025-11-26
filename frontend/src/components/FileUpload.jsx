import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';

const FileUpload = ({ onCheckUpload, onRemittanceUpload, onBothUpload, onBatchUpload, loading }) => {
  const [checkFile, setCheckFile] = useState(null);
  const [remittanceFile, setRemittanceFile] = useState(null);
  const [batchFiles, setBatchFiles] = useState([]);

  const onCheckDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setCheckFile(file);
      if (onCheckUpload) {
        onCheckUpload(file);
      }
    }
  }, [onCheckUpload]);

  const onRemittanceDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      setRemittanceFile(file);
      if (onRemittanceUpload) {
        onRemittanceUpload(file);
      }
    }
  }, [onRemittanceUpload]);

  const onBothDrop = useCallback((acceptedFiles) => {
    const imageFiles = acceptedFiles.filter(f => f.type.startsWith('image/'));
    const pdfFiles = acceptedFiles.filter(f => f.type === 'application/pdf');
    
    if (imageFiles.length > 0) {
      setCheckFile(imageFiles[0]);
    }
    if (pdfFiles.length > 0) {
      setRemittanceFile(pdfFiles[0]);
    }
    
    if (imageFiles.length > 0 || pdfFiles.length > 0) {
      if (onBothUpload) {
        onBothUpload(imageFiles[0] || null, pdfFiles[0] || null);
      }
    }
  }, [onBothUpload]);

  const checkDropzone = useDropzone({
    onDrop: onCheckDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp']
    },
    multiple: false,
    disabled: loading
  });

  const remittanceDropzone = useDropzone({
    onDrop: onRemittanceDrop,
    accept: {
      'application/pdf': ['.pdf']
    },
    multiple: false,
    disabled: loading
  });

  const bothDropzone = useDropzone({
    onDrop: onBothDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp'],
      'application/pdf': ['.pdf']
    },
    multiple: true,
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
      'image/*': ['.png', '.jpg', '.jpeg', '.gif', '.bmp'],
      'application/pdf': ['.pdf']
    },
    multiple: true,
    disabled: loading
  });

  const clearFiles = () => {
    setCheckFile(null);
    setRemittanceFile(null);
  };

  return (
    <div className="file-upload-container">
      <h2>Upload Documents</h2>
      
      <div className="upload-options">
        <div className="upload-section">
          <h3>Check Image Only</h3>
          <div {...checkDropzone.getRootProps()} className={`dropzone ${checkDropzone.isDragActive ? 'active' : ''}`}>
            <input {...checkDropzone.getInputProps()} />
            {checkFile ? (
              <div className="file-info">
                <p>✓ {checkFile.name}</p>
                <button onClick={(e) => { e.stopPropagation(); setCheckFile(null); }}>Remove</button>
              </div>
            ) : (
              <p>Drag & drop a check image here, or click to select</p>
            )}
          </div>
        </div>

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
          <h3>Both Files Together</h3>
          <div {...bothDropzone.getRootProps()} className={`dropzone ${bothDropzone.isDragActive ? 'active' : ''}`}>
            <input {...bothDropzone.getInputProps()} />
            {(checkFile || remittanceFile) ? (
              <div className="file-info">
                {checkFile && <p>✓ Check: {checkFile.name}</p>}
                {remittanceFile && <p>✓ Remittance: {remittanceFile.name}</p>}
                <button onClick={(e) => { e.stopPropagation(); clearFiles(); }}>Clear All</button>
              </div>
            ) : (
              <p>Drag & drop both files here (image + PDF), or click to select</p>
            )}
          </div>
        </div>

        <div className="upload-section">
          <h3>Batch Upload (Multiple Files)</h3>
          <p className="upload-hint">Upload multiple checks/remittances to process separately</p>
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
              <p>Drag & drop multiple files here (images and/or PDFs), or click to select</p>
            )}
          </div>
        </div>
      </div>

      {loading && (
        <div className="loading-indicator">
          <p>Processing files...</p>
        </div>
      )}
    </div>
  );
};

export default FileUpload;

