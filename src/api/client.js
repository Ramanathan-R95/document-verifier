import axios from 'axios';

const API_BASE_URL = '/api';

const client = axios.create({
  baseURL: API_BASE_URL,
  // OCR and image analysis can legitimately take longer than a standard API call.
  timeout: 120000,
});

/**
 * Upload a document
 */
export const uploadDocument = async (file, documentType) => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('documentType', documentType);

  return client.post('/documents/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

/**
 * Start a screening analysis
 */
export const startScreening = async (documentId, personPhotoId) => {
  return client.post('/screening/analyze', {
    documentId,
    personPhotoId,
  });
};

/**
 * Get screening results
 */
export const getScreeningResults = async (screeningCaseId) => {
  return client.get(`/screening/${screeningCaseId}`);
};

/**
 * List all screening cases
 */
export const listScreeningCases = async () => {
  return client.get('/screening');
};

/**
 * Health check
 */
export const healthCheck = async () => {
  return client.get('/health');
};

export default client;
