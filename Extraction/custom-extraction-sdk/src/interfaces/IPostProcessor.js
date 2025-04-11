class IPostProcessor {
  /**
   * Post-process the extracted data into standardized chunks
   * @param {Object} extractedData - The raw extracted data
   * @returns {Array} Array of chunk objects
   */
  async postProcess(extractedData) {
    throw new Error('Method not implemented');
  }

  /**
   * Format the final response with processed chunks
   * @param {Object} requestWrapper - The request wrapper object
   * @param {Array} chunks - The processed chunks
   * @returns {Object} Formatted response payload
   */
  async formatResponse(requestWrapper, chunks) {
    throw new Error('Method not implemented');
  }
}

module.exports = IPostProcessor; 