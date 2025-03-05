const CustomPreProcessor = require('./implementations/CustomPreProcessor');
const CustomExtractionLogic = require('./implementations/CustomExtractionLogic');
const CustomPostProcessor = require('./implementations/CustomPostProcessor');
const CallbackService = require('./services/CallbackService');

class ExtractionOrchestrator {
  constructor() {
    this.preProcessor = new CustomPreProcessor();
    this.extractionLogic = new CustomExtractionLogic();
    this.postProcessor = new CustomPostProcessor();
    this.callbackService = new CallbackService();
  }

  async process(headers, body, files, postProcessType = 'builder') {
    try {
      // Pre-processing
      const requestWrapper = this.preProcessor.process(headers, body, files);

      // Extraction
      const extractedData = await this.extractionLogic.extract(requestWrapper);

      // Post-processing
      const postProcessMethod = this.getPostProcessMethod(postProcessType);
      const callbackPayload = await postProcessMethod(extractedData);

      // Send callback
      await this.callbackService.sendCallback(
        callbackPayload,
        requestWrapper.getCallbackUrl()
      );

      return { success: true };
    } catch (error) {
      console.error('Extraction failed:', error);
      throw error;
    }
  }

  getPostProcessMethod(type) {
    switch (type) {
      case 'json':
        return this.postProcessor.postProcessJson.bind(this.postProcessor);
      case 'builder':
      default:
        return this.postProcessor.postProcessBuilder.bind(this.postProcessor);
    }
  }
}

// Usage example
async function demo() {
  const orchestrator = new ExtractionOrchestrator();

  const mockHeaders = {
    'x-trace-id': 'trace-123',
    'x-callback-url': 'http://callback-url.com'
  };

  const mockBody = {
    document_meta: 'test document',
    strategyBatchId: 'batch-123',
    docId: 'doc-123',
    streamId: 'stream-123',
    metadata: { type: 'test' }
  };

  const mockFiles = {
    upload: {
      name: 'test.pdf',
      path: '/tmp/test.pdf'
    }
  };

  try {
    await orchestrator.process(mockHeaders, mockBody, mockFiles);
    console.log('Processing completed successfully');
  } catch (error) {
    console.error('Demo failed:', error);
  }
}

demo(); 