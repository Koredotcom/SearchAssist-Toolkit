const IPreProcessor = require('../interfaces/IPreProcessor');
const RequestWrapper = require('../utils/RequestWrapper');

class CustomPreProcessor extends IPreProcessor {
  constructor() {
    super();
    this.mappings = {
      headers: {
        traceId: 'x-trace-id',
        callbackUrl: 'x-callback-url'
      },
      body: {
        documentMeta: 'document_meta',
        strategyBatchId: 'strategyBatchId',
        docId: 'docId',
        streamId: 'streamId',
        metadata: 'metadata'
      },
      files: {
        document: 'upload'
      }
    };
  }

  process(headers, body, files) {
    const requestWrapper = new RequestWrapper(headers, body, files);
    requestWrapper.setMappings(this.mappings);
    return requestWrapper;
  }
}

module.exports = CustomPreProcessor; 