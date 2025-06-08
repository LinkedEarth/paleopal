// API configuration for PaleoPal frontend
const API_CONFIG = {
  // In production/Docker, use relative URLs to go through nginx proxy
  // In development, use localhost
  BASE_URL: process.env.REACT_APP_API_URL || 
            (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000'),
  
  // API endpoints
  ENDPOINTS: {
    CONVERSATIONS: '/api/conversations',
    MESSAGES: '/api/messages',
    AGENTS: '/api/agents',
    HEALTH: '/api/health',
    LIBRARIES: '/api/libraries',
    EXTRACT: '/api/extract'
  }
};

// Debug logging
console.log('🔧 API Configuration:', {
  BASE_URL: API_CONFIG.BASE_URL,
  REACT_APP_API_URL: process.env.REACT_APP_API_URL,
  NODE_ENV: process.env.NODE_ENV,
  usingRelativeURLs: API_CONFIG.BASE_URL === ''
});

// Helper function to build API URLs
export const buildApiUrl = (endpoint, params = '') => {
  const baseUrl = API_CONFIG.BASE_URL;
  const fullUrl = `${baseUrl}${endpoint}${params}`;
  console.log(`🔗 Building URL: ${endpoint} -> ${fullUrl}`);
  return fullUrl;
};

// Helper function for making API requests with proper error handling
export const apiRequest = async (url, options = {}) => {
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    }
  };
  
  const finalOptions = { ...defaultOptions, ...options };
  
  try {
    console.log(`🚀 Making API request to: ${url}`, finalOptions);
    const response = await fetch(url, finalOptions);
    console.log(`📡 API response status: ${response.status} ${response.statusText}`);
    
    if (!response.ok) {
      throw new Error(`API request failed: ${response.status} ${response.statusText}`);
    }
    
    // Handle empty responses
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      const jsonResult = await response.json();
      console.log(`📋 JSON response:`, jsonResult);
      return jsonResult;
    } else {
      const textResult = await response.text();
      console.log(`📝 Text response:`, textResult);
      return textResult;
    }
  } catch (error) {
    console.error('❌ API request error:', error);
    throw error;
  }
};

// Test function to check API connectivity
export const testApiConnectivity = async () => {
  try {
    console.log('🧪 Testing API connectivity...');
    const healthUrl = buildApiUrl(API_CONFIG.ENDPOINTS.HEALTH);
    const result = await apiRequest(healthUrl);
    console.log('✅ API connectivity test passed:', result);
    return true;
  } catch (error) {
    console.error('❌ API connectivity test failed:', error);
    return false;
  }
};

export default API_CONFIG; 