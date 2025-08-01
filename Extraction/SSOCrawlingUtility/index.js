const puppeteer = require('puppeteer');
const cheerio = require('cheerio');
const fs = require('fs');
const url = require('url');
const path = require('path');
const processData = require('./processData');
const logger = require('./utils/logger');

// Load crawler configuration
const crawlerConfig = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'config', 'crawler.json'), 'utf-8'));

const profileDirectory = path.join(process.cwd(), crawlerConfig.outputDirectories.chromeProfile);
const htmlsDirectory = path.join(process.cwd(), crawlerConfig.outputDirectories.html);

// Ensure required directories exist
Object.values(crawlerConfig.outputDirectories).forEach(dir => {
    const dirPath = path.join(process.cwd(), dir);
    if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
    }
});

const visitedUrls = new Set();
const externalUrls = new Set();

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

const shouldCrawlUrl = (currentUrl, patterns = []) => {
    try {
        if (patterns.length == 0) return true;
        return patterns.some(pattern => currentUrl.includes(pattern));
    } catch (error) {
        logger.error(`Error checking URL: ${error.message}`);
        return false;
    }
};

const calculateDepth = (currentUrl, baseUrl) => {
    try {
        const basePath = new URL(baseUrl).pathname;
        const currentPath = new URL(currentUrl).pathname;

        const depth = currentPath.startsWith(basePath)
            ? currentPath.replace(basePath, '').split('/').filter(Boolean).length
            : 0;
        return depth;
    } catch (error) {
        logger.error(`Error calculating depth: ${error.message}`);
        return -1;
    }
};

// Manual login process and storing the session data
const manualLogin = async (page, loginUrl) => {
    try {
        await delay(20000);
        await page.goto(loginUrl, { waitUntil: 'networkidle0' });
        logger.info("Please complete the login manually in the browser, and then press Enter in this terminal after completing the login");

        // Wait for the user to press Enter after completing login
        await new Promise(resolve => {
            process.stdin.once('data', resolve); // Wait for user to press Enter
        });

        logger.info("Login completed, saving session.");
        await delay(20000);

        // Save cookies after login
        const cookies = await page.cookies();
        fs.writeFileSync('cookies.json', JSON.stringify(cookies));
    } catch (error) {
        logger.error(`Error during manual login: ${error.message}`);
        throw error;
    }
};

const loadCookies = async (page) => {
    try {
        const cookies = JSON.parse(fs.readFileSync('cookies.json', 'utf-8'));
        await page.setCookie(...cookies);
        logger.info('Cookies loaded successfully');
    } catch (error) {
        logger.error(`Error loading cookies: ${error.message}`);
    }
};

let urlCount = 0;

const crawlPageDFS = async (page, currentUrl, baseUrl, maxDepth, maxUrls, urlPatterns, parentUrl = null) => {
    try {
        // Stop crawling if the maximum number of URLs has been reached
        if (urlCount >= maxUrls) {
            return false;
        }

        const depth = calculateDepth(currentUrl, baseUrl);
        if (depth > maxDepth) {
            logger.info(`Skipping ${currentUrl} (depth: ${depth})`);
            return false; // Don't proceed with further crawling
        }

        await page.goto(currentUrl, { waitUntil: 'networkidle0', timeout: 0 });

        // Log the current URL and its parent for tracking the DFS order
        logger.info(`Crawling ${currentUrl}`, { parentUrl });

        // Increment the URL count
        urlCount++;

        const htmlContent = await page.content();
        await processData({ url: currentUrl, html: htmlContent });

        const fileName = currentUrl.replace(/[^a-zA-Z0-9]/g, '_') + '.html';
        const filePath = path.join(htmlsDirectory, fileName);
        fs.writeFileSync(filePath, htmlContent);
        logger.info(`Saved HTML content from ${currentUrl} to ${fileName}`);

        const $ = cheerio.load(htmlContent);
        let childUrls = [];

        $("a[href]").each((_, element) => {
            const link = $(element).attr("href");
            const absoluteLink = url.resolve(currentUrl, link);
            const parsedLink = new URL(absoluteLink);
            const currentDomain = new URL(baseUrl).hostname;

            if (parsedLink.hostname === currentDomain) {
                if (shouldCrawlUrl(absoluteLink, urlPatterns) && !visitedUrls.has(absoluteLink)) {
                    visitedUrls.add(absoluteLink);
                    // Add to the list of child URLs to be crawled
                    childUrls.push(absoluteLink);
                }
            } else {
                externalUrls.add(absoluteLink);
            }
        });

        // Process child URLs in DFS order
        for (let childUrl of childUrls) {
            if (urlCount >= maxUrls) {
                break;
            }
            await delay(20000);
            await crawlPageDFS(page, childUrl, baseUrl, maxDepth, maxUrls, urlPatterns, currentUrl);
        }

        return true;

    } catch (error) {
        logger.error(`Error crawling ${currentUrl}: ${error.message}`);
        return false;
    }
};

const startCrawlingDFS = async (page, currentUrl, baseUrl, maxDepth, maxUrls, urlPatterns, parentUrl = null) => {
    try {
        // Stop crawling if the maximum number of URLs has been reached
        if (urlCount >= maxUrls) {
            return false;
        }

        const depth = calculateDepth(currentUrl, baseUrl);
        if (depth > maxDepth) {
            logger.info(`Skipping ${currentUrl} (depth: ${depth})`);
            return false; // Don't proceed with further crawling
        }

        await page.goto(currentUrl, { waitUntil: 'networkidle0', timeout: 0 });

        // Log the current URL and its parent for tracking the DFS order
        logger.info(`Crawling ${currentUrl}`, { parentUrl });

        // Increment the URL count
        urlCount++;

        const htmlContent = await page.content();
        await processData({ url: currentUrl, html: htmlContent });

        const fileName = currentUrl.replace(/[^a-zA-Z0-9]/g, '_') + '.html';
        const filePath = path.join(htmlsDirectory, fileName);
        fs.writeFileSync(filePath, htmlContent);
        logger.info(`Saved HTML content from ${currentUrl} to ${fileName}`);

        const $ = cheerio.load(htmlContent);
        let childUrls = [];

        $("a[href]").each((_, element) => {
            const link = $(element).attr("href");
            const absoluteLink = url.resolve(currentUrl, link);
            const parsedLink = new URL(absoluteLink);
            const currentDomain = new URL(baseUrl).hostname;

            if (parsedLink.hostname === currentDomain) {
                if (shouldCrawlUrl(absoluteLink, urlPatterns) && !visitedUrls.has(absoluteLink)) {
                    visitedUrls.add(absoluteLink);
                    // Add to the list of child URLs to be crawled
                    childUrls.push(absoluteLink);
                }
            } else {
                externalUrls.add(absoluteLink);
            }
        });

        // Process child URLs in DFS order
        for (let childUrl of childUrls) {
            if (urlCount >= maxUrls) {
                break;
            }
            await delay(20000);
            await crawlPageDFS(page, childUrl, baseUrl, maxDepth, maxUrls, urlPatterns, currentUrl);
        }

        return true;

    } catch (error) {
        logger.error(`Error crawling ${currentUrl}: ${error.message}`);
        return false;
    }
};

const startCrawling = async () => {
    logger.info('Starting crawler with configuration', { config: crawlerConfig.sites });

    const browser = await puppeteer.launch({
        executablePath: crawlerConfig.browser.chromePath,
        headless: crawlerConfig.browser.headless,
        args: [
            `--user-data-dir=${profileDirectory}`,
            ...crawlerConfig.browser.args
        ]
    });

    const page = await browser.newPage();

    // Set User-Agent to a common one
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36');

    // Prevent detection by overriding the `navigator.webdriver`
    await page.evaluateOnNewDocument(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    });

    for (const site of crawlerConfig.sites) {
        if (!site.enabled) {
            logger.info(`Skipping disabled site: ${site.url}`);
            continue;
        }

        logger.info(`Starting to crawl site: ${site.url}`, {
            maxDepth: site.maxDepth,
            maxPages: site.maxPages
        });

        // Reset counters for each site
        urlCount = 0;
        visitedUrls.clear();
        externalUrls.clear();

        try {
            // Manual login step (if required)
            await manualLogin(page, site.url);

            visitedUrls.add(site.url);

            // Load cookies from previous session if any
            await loadCookies(page);

            await startCrawlingDFS(
                page,
                site.url,
                site.url,
                site.maxDepth,
                site.maxPages,
                site.urlPatterns
            );
        } catch (error) {
            logger.error(`Error crawling site: ${site.url}`, { error: error.message });
        }

        // Add delay between sites
        if (crawlerConfig.sites.indexOf(site) < crawlerConfig.sites.length - 1) {
            logger.info(`Waiting ${crawlerConfig.delay}ms before crawling next site`);
            await delay(crawlerConfig.delay);
        }
    }

    await browser.close();
    logger.info('Crawler finished processing all sites');
};

// Start the crawling process
startCrawling();