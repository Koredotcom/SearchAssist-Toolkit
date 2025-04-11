const http = require('http');
const ExtractionController = require('./controllers/ExtractionController');
const { SERVER } = require('./config/config');

class Server {
  constructor() {
    this.extractionController = new ExtractionController();
  }

  start() {
    const server = http.createServer((req, res) => {
      this.extractionController.handleRequest(req, res)
        .catch(error => {
          console.error('Unhandled server error:', error);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ 
            error: 'Internal Server Error',
            message: error.message 
          }));
        });
    });

    server.listen(SERVER.PORT, () => {
      console.log(`Server listening on http://localhost:${SERVER.PORT}${SERVER.BASE_PATH}`);
    });

    server.on('error', (error) => {
      console.error('Server failed to start:', error);
      process.exit(1);
    });
  }
}

new Server().start(); 