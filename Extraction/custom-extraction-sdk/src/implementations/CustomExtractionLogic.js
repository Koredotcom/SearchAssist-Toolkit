const IExtractionLogic = require('../interfaces/IExtractionLogic');
const config = require('../config/config');
const ShareConstants = require('../constants/ShareConstants');

class CustomExtractionLogic extends IExtractionLogic {
  async extract(requestWrapper) {
    const sys_content_type = requestWrapper.getSysContentType();
    const strategy = this.getStrategy(sys_content_type);
    return strategy.execute(requestWrapper);
  }

  getStrategy(sys_content_type) {
    const { CONFIGURED_CONNECTORS, AIRBYTE_CONNECTORS } = config.CONNECTORS;
    switch (sys_content_type) {
      case 'file':
        return new FileExtractionStrategy();
      case 'web':
        return new WebExtractionStrategy();
      case 'data':
        return new DataExtractionStrategy();
      case 'faq':
        return new FaqExtractionStrategy();
      default:
        if (CONFIGURED_CONNECTORS.includes(sys_content_type) || 
            AIRBYTE_CONNECTORS.includes(sys_content_type)) {
          return new ConnectorExtractionStrategy(sys_content_type);
        }
        throw new Error(`Unsupported sys_content_type: ${sys_content_type}`);
    }
  }
}

// Strategy Interface
class ExtractionStrategy {
  execute(requestWrapper) {
    throw new Error('Method not implemented');
  }
}

// Concrete Strategies
class FileExtractionStrategy extends ExtractionStrategy {
  execute(requestWrapper) {
    var file_title = requestWrapper.getFileTitle();
    var file_content = requestWrapper.getFileContent();
    var file_content_object = requestWrapper.getFileContentObject();
    var file_url = requestWrapper.getFileUrl();
    // Download the file and save it to the local file system
    var download_path = this.downloadFile(file_url);
    return this.extractChunks(file_content_object, file_title, file_url, downloadPath);  }

  downloadFile(file_url) {
    const fs = require('fs');
    const https = require('https');
    const path = require('path');

    // Generate a unique filename
    const uniqueNumber = Date.now();
    const tempFileName = `tempfile${uniqueNumber}`;
    const downloadPath = path.join(__dirname, tempFileName);

    const file = fs.createWriteStream(downloadPath);
    https.get(file_url, function(response) {
      response.pipe(file);
      file.on('finish', function() {
        file.close();  // close() is async, call cb after close completes.
        console.log(`Downloaded file saved as ${downloadPath}`);
      });
    }).on('error', function(err) { // Handle errors
      fs.unlink(downloadPath); // Delete the file async. (But we don't check the result)
      console.error(`Error downloading file: ${err.message}`);
    });
    return downloadPath;
  }

  extractChunks(file_content_object, file_title, file_url, downloadPath){
    console.log("file_content_object", file_content_object);
    console.log("file_title", file_title);
    console.log("file_url", file_url);
    console.log("downloadPath", downloadPath);
    //Your Extraction Logic Here
    return [{ chunkText: "File extraction", chunkTitle: "File" }];
  }
}

class WebExtractionStrategy extends ExtractionStrategy {
  execute(requestWrapper) {
    // Implement web extraction logic
    return [{ chunkText: "Web extraction", chunkTitle: "Web" }];
  }
}

class DataExtractionStrategy extends ExtractionStrategy {
  execute(requestWrapper) {
    // Implement data extraction logic
    return [{ chunkText: "Data extraction", chunkTitle: "Data" }];
  }
}

class FaqExtractionStrategy extends ExtractionStrategy {
  execute(requestWrapper) {
    // Implement FAQ extraction logic
    return [{ chunkText: "FAQ extraction", chunkTitle: "FAQ" }];
  }
}

class ConnectorExtractionStrategy extends ExtractionStrategy {
  constructor(sys_content_type) {
    super();
    this.sys_content_type = sys_content_type;
  }

  execute(requestWrapper) {
    // Implement connector-specific extraction logic
    return [{ chunkText: `Connector extraction for ${this.sys_content_type}`, chunkTitle: "Connector" }];
  }
}

module.exports = CustomExtractionLogic; 