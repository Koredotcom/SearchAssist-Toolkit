const RequestProcessor = require('../interfaces/RequestProcessor');

class JsonRequestProcessor extends RequestProcessor {
  async parseRequest(req) {
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

  async processData(data, requestData) {
    return {
      fields: data,
      files: {}
    };
  }
}

module.exports = JsonRequestProcessor; 