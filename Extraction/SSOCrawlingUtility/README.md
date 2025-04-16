# SSO Crawling Utility

A robust web crawling utility designed to crawl websites, extract content, and ingest it into a search assist system. The crawler supports manual SSO login handling and implements a depth-first search (DFS) crawling strategy.

## Features

- Depth-first search (DFS) crawling strategy
- Manual SSO login support with cookie persistence
- Configurable crawling parameters (depth, max pages, URL patterns)
- HTML content extraction and processing
- Automatic data ingestion to search assist API
- Comprehensive logging system
- Chrome browser automation using Puppeteer
- Configurable delays between page visits
- External URL tracking

## Prerequisites

- Node.js (Latest LTS version recommended)
- Google Chrome browser

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

The crawler is configured through `config/crawler.json`. Here's an example configuration:

```json
{
    "sites": [
        {
            "url": "https://example.com",
            "maxDepth": 2,
            "maxPages": 3,
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
        "hostUrl": "your-searchAi-host-url",
        "streamId": "your-stream-id",
        "authToken": "your-auth-token",
        "timeout": 10000,
        "name": "SSO Crawler Utility"
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

- **sites**: Array of sites to crawl
  - `url`: Target website URL
  - `maxDepth`: Maximum crawling depth
  - `maxPages`: Maximum number of pages to crawl
  - `enabled`: Enable/disable crawling for this site
  - `urlPatterns`: Array of URL patterns to match for crawling

- **delay**: Delay between page visits (in milliseconds)
- **outputDirectories**: Directory configuration for outputs
- **ingest**: Search assist API configuration
- **browser**: Chrome browser configuration

## Usage

1. Configure the crawler by editing `config/crawler.json`

2. Start the crawler:
```bash
node index.js
```

3. When prompted for manual login:
   - The browser will open to the target URL
   - Complete the login process manually
   - Press Enter in the terminal to continue crawling

## Output

The crawler generates several outputs:

- **HTML Files**: Saved in the configured `htmls` directory
- **Logs**: Detailed crawling logs in the `logs` directory
- **Chrome Profile**: Browser session data in `chrome_profile` directory

## Project Structure

- `index.js`: Main crawler implementation
- `processData.js`: HTML content extraction and processing
- `ingestData.js`: Data ingestion to search assist API
- `utils/logger.js`: Logging utility
- `config/crawler.json`: Crawler configuration

## Dependencies

- `puppeteer`: Browser automation
- `cheerio`: HTML parsing and manipulation
- `axios`: HTTP client for API requests
- `dotenv`: Environment variable management

## Error Handling

The crawler includes comprehensive error handling and logging:
- Failed page loads
- Network errors
- Data processing errors
- API ingestion failures

Logs are saved with timestamps and detailed error information for debugging.

## Security Notes

- The crawler supports SSO authentication through manual login
- Cookies are saved for session persistence
- Auth tokens should be properly secured and not committed to version control
- Chrome is run with security-related arguments for safe automation

## License

ISC License 