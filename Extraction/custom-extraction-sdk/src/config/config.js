module.exports = {
  SERVER: {
    PORT: 6606,
    BASE_PATH: '/searchAssistant/checkCustom/'
  },
  API: {
    HEADERS: {
      API_KEY: 'yktyderjdzfwhhM3wQkjhsfiaHqSBxTpc4XXOP7v/rHdPYfD6qA9Zc='
    }
  },
  PROCESSING: {
    DELAY_MS: 10000
  },
  EXTERNAL_SERVICE: {
    BASE_URL: 'http://3.81.227.94:3000',
    ENDPOINTS: {
      PROCESS: '/process-directory-from-url',
      STATUS: '/file-status'
    },
    POLLING: {
      MAX_ATTEMPTS: 30,
      INTERVAL_MS: 5000,
      TIMEOUT_MS: 150000
    },
    DEFAULT_OPTIONS: {
      INCLUDE_BASE64: true
    }
  },
  ERROR_MESSAGES: {
    DOWNLOAD_URL_REQUIRED: 'Download URL is required',
    PROCESSING_FAILED: 'Processing failed',
    PROCESSING_TIMEOUT: 'Processing timeout',
    EXTERNAL_SERVICE_ERROR: 'External service error',
    STATUS_CHECK_ERROR: 'Error checking status',
    S3_FETCH_ERROR: 'Error fetching processed data'
  },
  CONNECTORS: {
    CONFIGURED_CONNECTORS: [
      'confluenceServer', 'confluenceCloud', 'serviceNow', 'zendesk', 
      'sharepointOnline', 'googleDrive', 'azureStorage', 'salesforce', 
      'oracleKnowledge', 'dropbox', 'dotCMS', 'customConnector'
    ],
    AIRBYTE_CONNECTORS: [
      'airtable', 'github', 'gitlab', 'greenhouse', 'hubspot', 'jira', 
      'marketo', 'monday', 'notion', 'slack', 'amazonAds', 
      'amazonSellerPartner', 'amplitude', 'azureBlobStorage', 'bingAds', 
      'chargebee', 'facebookMarketing', 'fileCsvJsonExcelFeatherParquet', 
      'freshdesk', 'googleAds', 'googleAnalytics4Ga4', 'googleSearchConsole', 
      'googleSheets', 'harvest', 'instagram', 'intercom', 'iterable', 
      'klaviyo', 'linkedinAds', 'mailchimp', 'microsoftSqlServer', 
      'mixpanel', 'mongodb', 'mysql', 'paypalTransaction', 'pinterest', 
      'postgres', 'recharge', 's3', 'sendgrid', 'sentry', 'shopify', 
      'snapchatMarketing', 'stripe', 'surveymonkey', 'tiktokMarketing', 
      'twilio', 'typeform', 'woocommerce'
    ]
  }
}; 