const axios = require('axios');
const { JSDOM } = require("jsdom");
require('dotenv').config();

class OneNoteExtractor {
    constructor(accessToken) {
        this.accessToken = accessToken;
        this.baseUrl = 'https://graph.microsoft.com/v1.0/me/onenote';
        this.headers = {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        };
    }

    async getNotebooks() {
        try {
            const response = await axios.get(`${this.baseUrl}/notebooks`, {
                headers: this.headers
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching notebooks:', error.message);
            throw error;
        }
    }

    async getSections(notebookId) {
        try {
            const response = await axios.get(`${this.baseUrl}/notebooks/${notebookId}/sections`, {
                headers: this.headers
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching sections:', error.message);
            throw error;
        }
    }

    async getPages(sectionId) {
        try {
            const response = await axios.get(`${this.baseUrl}/sections/${sectionId}/pages`, {
                headers: this.headers
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching pages:', error.message);
            throw error;
        }
    }

    async getPageContent(pageId) {
        try {
            const response = await axios.get(`${this.baseUrl}/pages/${pageId}/content`, {
                headers: this.headers
            });
            return response.data;
        } catch (error) {
            console.error('Error fetching page content:', error.message);
            throw error;
        }
    }

    async extractAllContent() {
        try {
            const allContent = [];
            // Get all notebooks
            const notebooks = await this.getNotebooks();
            
            for (const notebook of notebooks.value) {
                console.log(`Processing notebook: ${notebook.displayName}`);
                
                // Get sections for each notebook
                const sections = await this.getSections(notebook.id);
                
                for (const section of sections.value) {
                    console.log(`Processing section: ${section.displayName}`);
                    
                    // Get pages for each section
                    const pages = await this.getPages(section.id);
                    
                    for (const page of pages.value) {
                        console.log(`Processing page: ${page.title}`);
                        
                        // Get content for each page
                        const content = await this.getPageContent(page.id);
                        
                        allContent.push({
                            notebook: notebook.displayName,
                            section: section.displayName,
                            page: page.title,
                            content: content,
                            metadata: {
                                notebookId: notebook.id,
                                sectionId: section.id,
                                pageId: page.id,
                                doc_updated_on: page?.lastModifiedDateTime || page?.createdDateTime,
                                doc_created_on: page?.createdDateTime,
                                recordUrl: page?.links?.oneNoteWebUrl?.href || page?.links?.oneNoteClientUrl?.webUrl,
                                author: section?.createdBy?.user?.displayName
                            }
                        });
                    }
                }
            }
            
            return allContent;
        } catch (error) {
            console.error('Error in content extraction:', error.message);
            throw error;
        }
    }
}

function parseHtml(html){
    const dom = new JSDOM(html);
    return dom.window.document.body.textContent.trim();
}

async function formatContent(content){
    const formattedContent = []
    for(const item of content){
        const formattedItem = {
            chunkTitle: `${item.notebook} - ${item.section} - ${item.page}`,
            chunkText: parseHtml(item.content),
            recordUrl: item?.metadata?.recordUrl,
            cfs1: item?.section,
            cfs2: item?.metadata?.author,
            // cfs3: item?.notebook,
            // cfs5: item?.page,
            // html: item.content
        }
        formattedContent.push(formattedItem)
    }
    return formattedContent
}

// Example usage
async function executeExtraction() {
    try {
        const accessToken = process.env.ONE_NOTE_ACCESS_TOKEN;
        const extractor = new OneNoteExtractor(accessToken);
        const allContent = await extractor.extractAllContent();
        
        console.log(`Successfully extracted ${allContent.length} pages`);
        
        return allContent;
    } catch (error) {
        console.error('Extraction failed:', error);
        throw error;
    }
}

module.exports = {
    OneNoteExtractor,
    executeExtraction,
    formatContent
};
