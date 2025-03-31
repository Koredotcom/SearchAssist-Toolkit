const RequestProcessor = require('../interfaces/RequestProcessor');
const formidable = require('formidable');

class FormDataRequestProcessor extends RequestProcessor {
  async parseRequest(req) {
    return new Promise((resolve, reject) => {
      const form = new formidable.IncomingForm();
      form.parse(req, (err, fields, files) => {
        if (err) {
          reject({ statusCode: 400, message: 'Error parsing form data' });
          return;
        }
        resolve({ fields, files });
      });
    });
  }

  async processData(data, requestData) {
    return data;
  }
}

module.exports = FormDataRequestProcessor; 