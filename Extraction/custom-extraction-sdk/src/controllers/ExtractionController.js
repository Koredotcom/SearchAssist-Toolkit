const BaseController = require('./BaseController');
const formidable = require('formidable');
const CustomPreProcessor = require('../implementations/CustomPreProcessor');
const CustomExtractionLogic = require('../implementations/CustomExtractionLogic');
const CustomPostProcessor = require('../implementations/CustomPostProcessor');
const CallbackService = require('../services/CallbackService');

class ExtractionController extends BaseController {
  constructor() {
    super();
    this.preProcessor = new CustomPreProcessor();
    this.extractionLogic = new CustomExtractionLogic();
    this.postProcessor = new CustomPostProcessor(50);
    this.callbackService = new CallbackService();
  }

  async process(req, res) {
    const { method, headers } = req;

    if (method.toLowerCase() !== 'post') {
      return this.handleGetRequest(res);
    }

    try {
      const { body, files } = await this.parseRequest(req);
      
      // Validate required headers
      if (!headers['x-trace-id'] || !headers['x-callback-url']) {
        throw { statusCode: 400, message: 'Missing required headers (x-trace-id, x-callback-url)' };
      }

      // Acknowledge request immediately
      this.acknowledgeRequest(res);

      // Process in background
      this.scheduleProcessing(headers, body, files);

    } catch (error) {
      throw {
        statusCode: error.statusCode || 500,
        message: error.message || 'Error processing request'
      };
    }
  }

  async parseRequest(req) {
    const contentType = req.headers['content-type'] || '';

    if (contentType.includes('application/json')) {
      const body = await this.parseJsonRequest(req);
      return { body, files: {} };
    } 
    
    if (contentType.includes('multipart/form-data')) {
      return this.parseFormData(req);
    }

    throw { 
      statusCode: 415, 
      message: 'Content-Type must be application/json or multipart/form-data'
    };
  }

  async parseJsonRequest(req) {
    return new Promise((resolve, reject) => {
      let data = '';
      req.on('data', chunk => data += chunk);
      req.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (err) {
          reject({ statusCode: 400, message: 'Invalid JSON data' });
        }
      });
    });
  }

  async parseFormData(req) {
    return new Promise((resolve, reject) => {
      const form = new formidable.IncomingForm();
      form.parse(req, (err, fields, files) => {
        if (err) {
          reject({ statusCode: 400, message: 'Error parsing form data' });
          return;
        }
        resolve({ body: fields, files });
      });
    });
  }

  async scheduleProcessing(headers, body, files, type='builder') {
    setImmediate(async () => {
      try {
        // Pre-processing
        const requestWrapper = this.preProcessor.process(headers, body, files);

        // Extraction
        const extractedData = await this.extractionLogic.extract(requestWrapper);

        // Post-processing: First convert to chunks
        const chunks = await this.postProcessor.postProcess(extractedData, type);

        // Send chunks in batches
        await this.callbackService.sendBatchedCallback(
          this.postProcessor,
          requestWrapper,
          chunks,
          requestWrapper.getCallbackUrl()
        );
      } catch (error) {
        console.error('Background processing failed:', error);
      }
    });
  }

  acknowledgeRequest(res) {
    this.sendResponse(res, 202, {
      status: 'acknowledged',
      message: 'Your request is being processed'
    });
  }

  handleGetRequest(res) {
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`
      <form action="/" enctype="multipart/form-data" method="post">
        <input type="text" name="document_meta" placeholder="Document Meta" /><br />
        <input type="text" name="strategyBatchId" placeholder="Strategy Batch ID" /><br />
        <input type="text" name="docId" placeholder="Doc ID" /><br />
        <input type="text" name="streamId" placeholder="Stream ID" /><br />
        <input type="file" name="upload" multiple="multiple" /><br />
        <input type="submit" value="Upload" />
      </form>
    `);
  }
}

module.exports = ExtractionController; 