import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'multipart/form-data',
  },
});

export const uploadCheck = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/api/upload/check', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const uploadRemittance = async (file) => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await api.post('/api/upload/remittance', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const uploadBoth = async (checkFile, remittanceFile) => {
  const formData = new FormData();
  if (checkFile) {
    formData.append('check', checkFile);
  }
  if (remittanceFile) {
    formData.append('remittance', remittanceFile);
  }
  
  const response = await api.post('/api/upload/both', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const searchInvoices = async (params) => {
  const response = await api.get('/api/invoices/search', { params });
  return response.data;
};

export const getInvoice = async (invoiceId) => {
  const response = await api.get(`/api/invoices/${invoiceId}`);
  return response.data;
};

