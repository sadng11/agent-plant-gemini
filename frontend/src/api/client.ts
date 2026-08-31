import axios, { type InternalAxiosRequestConfig } from 'axios';

interface RetryAxiosRequestConfig extends InternalAxiosRequestConfig {
  _retryCount?: number;
}

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000,
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config as RetryAxiosRequestConfig;

    // Auto-retry on network errors, timeout or 5xx/429 status codes up to 2 times
    if (
      config &&
      (!error.response || error.response.status >= 500 || error.response.status === 429 || error.code === 'ECONNABORTED')
    ) {
      config._retryCount = config._retryCount || 0;
      if (config._retryCount < 2) {
        config._retryCount += 1;
        const delayMs = config._retryCount * 1500;
        await new Promise((resolve) => setTimeout(resolve, delayMs));
        return apiClient(config);
      }
    }

    const errorMsg = error.response?.data?.detail || error.message || 'خطای ناشناخته در ارتباط با سرور';
    console.error('API Error:', errorMsg, error);
    return Promise.reject(error);
  }
);
