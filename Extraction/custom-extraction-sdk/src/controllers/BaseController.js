class BaseController {
  async handleRequest(req, res) {
    try {
      if (!this.process) {
        throw new Error('Process method must be implemented');
      }
      console.log('Processing request:', {
        method: req.method,
        url: req.url,
        headers: {
          'content-type': req.headers['content-type'],
          'x-trace-id': req.headers['x-trace-id'],
          'x-callback-url': req.headers['x-callback-url']
        }
      });
      await this.process(req, res);
    } catch (error) {
      this.handleError(res, error);
    }
  }

  handleError(res, error) {
    const statusCode = error.statusCode || 500;
    const errorMessage = error.message || 'Internal Server Error';
    
    console.error('Error:', { 
      statusCode, 
      message: errorMessage,
      stack: error.stack 
    });
    
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      error: errorMessage
    }));
  }

  sendResponse(res, statusCode, data) {
    res.writeHead(statusCode, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(data));
  }
}

module.exports = BaseController; 