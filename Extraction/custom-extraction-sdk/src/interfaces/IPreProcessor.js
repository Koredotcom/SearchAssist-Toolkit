class IPreProcessor {
  getRequestHeaders() {
    throw new Error('Method not implemented');
  }

  getRequestBody() {
    throw new Error('Method not implemented');
  }

  getRequestFiles() {
    throw new Error('Method not implemented');
  }
}

module.exports = IPreProcessor; 