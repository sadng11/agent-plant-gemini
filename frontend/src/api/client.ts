import axios from 'axios';

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMsg = error.response?.data?.detail || error.message || 'خطای ناشناخته در ارتباط با سرور';
    console.error('API Error:', errorMsg, error);
    return Promise.reject(error);
  }
);
