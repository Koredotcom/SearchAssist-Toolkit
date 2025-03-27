const axios = require('axios');
const { API } = require('../config/config');

class CallbackService {
  async sendCallback(payload, callbackUrl) {
    try {
      const response = await axios.post(callbackUrl, payload, {
        headers: {
          'Content-Type': 'application/json',
          'apikey': API.HEADERS.API_KEY,
          // 'x_api_key': API.HEADERS.X_API_KEY
        }
      });
      return response;
    } catch (error) {
      console.error('Callback error:', error.message);
      throw error;
    }
  }

  async sendBatchedCallback(postProcessor, requestWrapper, chunks, callbackUrl) {
    const totalBatches = postProcessor.getBatchCount(chunks);
    
    for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
      try {
        const batchPayload = await postProcessor.formatResponse(
          requestWrapper, 
          chunks, 
          batchIndex
        );
        
        await this.sendCallback(batchPayload, callbackUrl);
                
      } catch (error) {
        console.error(`Error sending batch ${batchIndex}:`, error);
        throw error;
      }
    }
  }
}

module.exports = CallbackService; 