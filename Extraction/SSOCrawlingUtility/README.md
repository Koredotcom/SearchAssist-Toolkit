# SSO Crawling Utility

A robust web crawling utility designed to crawl websites, extract content, and ingest it into search assist systems (XO11/UnifiedXO or XO10/SearchAssist). The crawler supports manual SSO login handling, implements a depth-first search (DFS) crawling strategy, and features efficient batch processing for data ingestion.

## Features

- **Depth-first search (DFS) crawling strategy** with configurable depth and page limits
- **Manual SSO login support** with cookie persistence and session management
- **Configurable crawling parameters** (depth, max pages, URL patterns)
- **HTML content extraction and processing** with Cheerio
- **Automatic data ingestion** to search assist APIs (XO11/UnifiedXO or XO10/SearchAssist)
- **Batch processing** with configurable batch sizes for efficient API usage
- **Chrome browser automation** using Puppeteer with anti-detection measures
- **Configurable delays** between page visits
- **External URL tracking** and filtering

## Prerequisites

- Node.js (Latest LTS version recommended)
- Google Chrome browser
- Valid authentication tokens for target search assist system

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd SSOCrawlingUtility
```

2. Install dependencies:
```bash
npm install
```

## Configuration

The crawler is configured through `config/crawler.json`. Here's a complete configuration example:

```json
{
    "sites": [
        {
            "url": "https://example.com",
            "maxDepth": 2,
            "maxPages": 50,
            "enabled": true,
            "urlPatterns": []
        }
    ],
    "delay": 20000,
    "outputDirectories": {
        "html": "htmls",
        "logs": "logs",
        "chromeProfile": "chrome_profile"
    },
    "ingest": {
        "isUnifiedXO":true,
        "hostUrl": "your-searchAi-host-url",
        "streamId": "your-stream-id",
        "authToken": "your-auth-token",
        "timeout": 10000,
        "name": "SSO Crawler Utility",
        "batchSize": 50,
        "apiUrls": {
            "uxo": "/api/public/bot/{streamId}/ingest-data",
            "searchAssist": "/searchassistapi/external/stream/{streamId}/ingest?contentSource=manual&extractionType=data&index=true"
        }
    },
    "browser": {
        "chromePath": "your-google-chrome",
        "headless": false,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
            // ... other Chrome arguments
        ]
    }
}
```

### Configuration Parameters

#### **sites**: Array of sites to crawl
- `url`: Target website URL
- `maxDepth`: Maximum crawling depth (0 = root only, 1 = root + direct links, etc.)
- `maxPages`: Maximum number of pages to crawl per site
- `enabled`: Enable/disable crawling for this site
- `urlPatterns`: Array of URL patterns to match for crawling (empty array = crawl all URLs)

#### **delay**: Delay between page visits (in milliseconds)
- Recommended: 20000ms (20 seconds) to avoid overwhelming servers

#### **outputDirectories**: Directory configuration for outputs
- `html`: Directory to save crawled HTML content
- `logs`: Directory for log files
- `chromeProfile`: Directory for Chrome user profile data

#### **ingest**: Search assist API configuration
- `isUnifiedXO`: Boolean flag to determine API type
  - `true`: Uses XO11/UnifiedXO API with chunk-based structure
  - `false`: Uses XO10/SearchAssist API with document-based structure
- `hostUrl`: Base URL for the search assist API
- `streamId`: Stream ID of the application
- `authToken`: Authentication token for API access
- `timeout`: API request timeout in milliseconds
- `name`: Name identifier for the crawler utility
- `batchSize`: Number of documents to process per batch (default: 50)
- `apiUrls`: API endpoint URLs for different platforms
  - `uxo`: UXO API endpoint template
  - `searchAssist`: SearchAssist API endpoint template

#### **browser**: Chrome browser configuration
- `chromePath`: Path to Chrome executable
- `headless`: Run browser in headless mode (true/false)
- `args`: Array of Chrome command-line arguments

## Usage

1. **Configure the crawler** by editing `config/crawler.json`:
   - Set your target URLs
   - Configure API credentials
   - Adjust crawling parameters
   - Set batch size for ingestion

2. **Start the crawler**:
```bash
node index.js
```

3. **Complete manual login** when prompted:
   - The browser will open to the target URL
   - Complete the SSO login process manually
   - Press Enter in the terminal to continue crawling

## How It Works

### **Crawling Process**
1. **DFS Traversal**: Uses depth-first search to crawl pages systematically
2. **URL Filtering**: Only crawls URLs matching specified patterns
3. **Depth Control**: Respects maximum depth limits
4. **Page Limits**: Stops when maximum pages are reached
5. **Session Management**: Maintains login session across pages

### **Batch Processing**
1. **Document Collection**: Collects processed documents in memory
2. **Batch Triggering**: Processes batches when `batchSize` is reached
3. **API Ingestion**: Sends documents to search assist API
4. **Memory Management**: Clears processed documents from memory
5. **Final Processing**: Handles remaining documents after crawling

### **Data Ingestion**

#### **For XO11/UnifiedXO (`isUnifiedXO: true`)**:
- Creates **single FileName** with **multiple chunks**
- Each crawled page becomes a chunk within one File
- Document title: `Crawled Pages_batch_{batchNumber}`
- Chunk title: Original page title

#### **For XO10/SearchAssist (`isUnifiedXO: false`)**:
- Creates **individual documents** for each page
- Each crawled page becomes a separate document
- Document title: Original page title
- Document content: Page content

## Output

The crawler generates several outputs:

- **HTML Files**: Saved in the configured `htmls` directory
- **Logs**: Detailed crawling logs in the `logs` directory
- **Chrome Profile**: Browser session data in `chrome_profile` directory
- **API Responses**: Logged with job IDs and status information

## Project Structure

```
SSOCrawlingUtility/
├── index.js              # Main crawler implementation
├── processData.js        # HTML content extraction and processing
├── ingestData.js         # Data ingestion to search assist API
├── utils/
│   └── logger.js         # Logging utility
├── config/
│   └── crawler.json      # Crawler configuration
├── htmls/                # Crawled HTML content
├── logs/                 # Log files
└── chrome_profile/       # Chrome user profile data
```

## Dependencies

- `puppeteer`: Browser automation and control
- `cheerio`: HTML parsing and content extraction
- `axios`: HTTP client for API requests
- `fs`: File system operations
- `path`: Path manipulation utilities

## Error Handling

The crawler includes comprehensive error handling and logging:

- **Failed page loads**: Logged with retry attempts
- **Network errors**: Graceful handling with timeouts
- **Data processing errors**: Detailed error messages
- **API ingestion failures**: Batch-level error handling
- **Memory management**: Automatic cleanup and monitoring

## Performance Features

- **Batch Processing**: Reduces API calls by grouping documents
- **Memory Efficiency**: Automatic cleanup after each batch
- **Configurable Delays**: Prevents server overload
- **Session Persistence**: Avoids repeated logins
- **Anti-Detection**: Chrome arguments to avoid bot detection

## Security Notes

- **SSO Authentication**: Supports complex login flows through manual interaction
- **Cookie Persistence**: Maintains session across crawling sessions
- **Secure Configuration**: Auth tokens should be properly secured
- **Chrome Security**: Runs with security-focused arguments
- **Network Isolation**: Uses separate Chrome profile for crawling

## Troubleshooting

### **Common Issues**

1. **Chrome Path Issues**:
   - Verify Chrome is installed and path is correct
   - Use `which google-chrome` to find path

2. **API Authentication**:
   - Check auth token validity
   - Verify stream ID and host URL

3. **Memory Issues**:
   - Reduce batch size if processing large sites
   - Monitor memory usage during crawling

4. **Network Timeouts**:
   - Increase timeout values in configuration
   - Check network connectivity

### **Log Analysis**

Logs provide detailed information about:
- Crawling progress and URLs visited
- Batch processing status
- API ingestion results
- Error details and stack traces

## License

ISC License 