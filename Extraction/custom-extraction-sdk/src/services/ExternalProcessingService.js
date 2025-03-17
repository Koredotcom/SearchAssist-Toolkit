const axios = require('axios');
const config = require('../config/config');

class ExternalProcessingService {
  constructor() {
    this.baseUrl = config.EXTERNAL_SERVICE.BASE_URL;
    this.endpoints = config.EXTERNAL_SERVICE.ENDPOINTS;
    this.polling = config.EXTERNAL_SERVICE.POLLING;
    this.errorMessages = config.ERROR_MESSAGES;
  }

  async initiateProcessing(downloadUrl) {
    try {
      const response = await axios.post(`${this.baseUrl}${this.endpoints.PROCESS}`, {
        downloadUrl,
        include_base64: config.EXTERNAL_SERVICE.DEFAULT_OPTIONS.INCLUDE_BASE64
      });
      return response.data;
    } catch (error) {
      if (error.response) {
        throw {
          status: error.response.status,
          message: error.response.data.message || this.errorMessages.EXTERNAL_SERVICE_ERROR
        };
      }
      throw error;
    }
  }

  async checkStatus(uniqueId) {
    try {
      const response = await axios.get(`${this.baseUrl}${this.endpoints.STATUS}/${uniqueId}`);
      return response.data;
    } catch (error) {
      if (error.response) {
        throw {
          status: error.response.status,
          message: error.response.data.message || this.errorMessages.STATUS_CHECK_ERROR
        };
      }
      throw error;
    }
  }

  async pollStatus(uniqueId) {
    let attempts = 0;
    
    while (attempts < this.polling.MAX_ATTEMPTS) {
      const statusResponse = await this.checkStatus(uniqueId);
      
      if (statusResponse.status === 'success' && statusResponse.data.status === 'completed') {
        return statusResponse.data;
      }
      
      if (statusResponse.status === 'error' || statusResponse.data.status === 'failed') {
        throw new Error(statusResponse.data.error || this.errorMessages.PROCESSING_FAILED);
      }
      
      await new Promise(resolve => setTimeout(resolve, this.polling.INTERVAL_MS));
      attempts++;
    }
    
    throw new Error(this.errorMessages.PROCESSING_TIMEOUT);
  }

  async fetchProcessedData(s3Url) {
    try {
      const response = await axios.get(s3Url);
      return response.data;
    } catch (error) {
      throw new Error(`${this.errorMessages.S3_FETCH_ERROR}: ${error.message}`);
    }
  }
}

module.exports = ExternalProcessingService; 