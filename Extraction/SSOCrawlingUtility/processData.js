const cheerio = require('cheerio');
const logger = require('./utils/logger');

async function extractPageData(htmlContent) {
    try {
        // Load HTML into cheerio
        const $ = cheerio.load(htmlContent);

        // Extract title before removing elements
        const title = $('title').text().trim() || $('h1').first().text().trim() || null;

        // Remove unwanted elements
        $('script, style, nav, noscript, header, footer, aside, [aria-label="Main navigation"], .nav, .sidebar, .menu').remove();

        // Extract and clean main content
        const mainContent = $('body').text().replace(/\s+/g, ' ').trim();

        return {
            title,
            content: mainContent || null
        };
    } catch (error) {
        logger.error('Error processing HTML:', { error: error.message });
        return {
            title: null,
            content: null
        };
    }
}

async function processData({url, html}) {
    logger.debug('Processing data', { url });
    const { title, content } = await extractPageData(html);
    
    const documentObject = {
        "url": url,
        "title": title,
        "content": content
    }

    if (!content) {
        logger.warn('No content extracted from page', { url });
    }
    if (!title) {
        logger.warn('No title found for page', { url });
    }

    // Return the document object instead of ingesting immediately
    return documentObject;
}

module.exports = processData;
