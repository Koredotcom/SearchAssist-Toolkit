const IExtractionLogic = require('../interfaces/IExtractionLogic');
const config = require('../config/config');

class CustomExtractionLogic extends IExtractionLogic {
  constructor() {
    super();
  }

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
    // Implement web extraction logic
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