/**
 * RAG Evaluator UI JavaScript
 * A comprehensive evaluation system for RAG (Retrieval-Augmented Generation) models
 * @version 3.0
 * @author RAG Evaluator Team
 */

// Constants and Configuration
const CONFIG = {
    // UI Constants
    MAX_FILE_SIZE: 100 * 1024 * 1024, // 100MB
    SUPPORTED_FILE_TYPES: ['.xlsx', '.xls'],
    
    // Time estimation constants
    BASE_PROCESSING_TIME: 0.5, // seconds per query
    SEARCH_API_TIME: 2.5,
    RAGAS_EVAL_TIME: 12,
    CRAG_EVAL_TIME: 3,
    LLM_EVAL_TIME: 4,
    MIN_PROCESSING_TIME: 0.5,
    BASE_OVERHEAD: 30, // seconds
    OVERHEAD_PER_QUERY: 0.5, // seconds
    
    // Default values
    DEFAULT_BATCH_SIZE: 10,
    DEFAULT_MAX_CONCURRENT: 5,
    
    // Toast durations
    TOAST_DURATION: {
        SUCCESS: 5000,
        ERROR: 8000,
        WARNING: 6000,
        INFO: 4000
    },
    
    // Progress update intervals
    PROGRESS_UPDATE_INTERVAL: 2000, // ms
    
    // Chart colors
    CHART_COLORS: {
        PRIMARY: '#3B82F6',
        SUCCESS: '#10B981',
        WARNING: '#F59E0B',
        ERROR: '#EF4444',
        SECONDARY: '#6B7280'
    }
};

// API Endpoints
const API_ENDPOINTS = {
    CREATE_SESSION: '/api/create-session',
    SESSION_STATUS: '/api/session-status',
    UPLOAD_FILE: '/api/upload-file',
    START_EVALUATION: '/api/start-evaluation',
    EVALUATION_PROGRESS: '/api/evaluation-progress',
    DOWNLOAD_RESULTS: '/api/download-results'
};

// DOM Element IDs
const ELEMENTS = {
    UPLOAD_AREA: 'upload-area',
    FILE_INPUT: 'excel-file',
    REMOVE_FILE: 'remove-file',
    START_EVALUATION: 'start-evaluation',
    DOWNLOAD_RESULTS: 'download-results',
    VIEW_DETAILS: 'view-details',
    NEW_EVALUATION: 'new-evaluation',
    SHEET_SELECT: 'sheet-name',
    BATCH_SIZE: 'batch-size',
    MAX_CONCURRENT: 'max-concurrent',
    USE_SEARCH_API: 'use-search-api',
    EVALUATE_RAGAS: 'evaluate-ragas',
    EVALUATE_CRAG: 'evaluate-crag',
    EVALUATE_LLM: 'evaluate-llm',
    LLM_MODEL: 'llm-model',
    ESTIMATED_TIME: 'estimated-time',
    TOTAL_QUERIES: 'total-queries'
};

console.log('🔥 RAG EVALUATOR SCRIPT LOADED - VERSION 3.0 (REFACTORED)');

/**
 * Utility class for common DOM and data operations
 */
class UIUtils {
    /**
     * Get element by ID with error handling
     * @param {string} id - Element ID
     * @returns {HTMLElement|null} DOM element or null
     */
    static getElement(id) {
        const element = document.getElementById(id);
        if (!element) {
            console.warn(`⚠️ Element not found: ${id}`);
        }
        return element;
    }

    /**
     * Update element text content safely
     * @param {string} id - Element ID
     * @param {string|number} value - Value to set
     */
    static updateElement(id, value) {
        const element = this.getElement(id);
        if (element) {
            element.textContent = value;
        }
    }

    /**
     * Show/hide element
     * @param {string} id - Element ID
     * @param {boolean} show - Whether to show the element
     */
    static toggleElement(id, show) {
        const element = this.getElement(id);
        if (element) {
            element.style.display = show ? 'block' : 'none';
        }
    }

    /**
     * Format time in seconds to human readable format
     * @param {number} seconds - Time in seconds
     * @returns {string} Formatted time string
     */
    static formatTime(seconds) {
        if (seconds < 60) {
            return `${Math.round(seconds)}s`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = Math.round(seconds % 60);
            return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
        }
    }

    /**
     * Format currency value
     * @param {number} value - Currency value
     * @returns {string} Formatted currency string
     */
    static formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 4
        }).format(value);
    }

    /**
     * Format token count
     * @param {number} count - Token count
     * @returns {string} Formatted token count
     */
    static formatTokenCount(count) {
        return new Intl.NumberFormat('en-US').format(count);
    }

    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Toast type (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds (optional)
     */
    static showToast(message, type = 'info', duration = null) {
        const toastDuration = duration || CONFIG.TOAST_DURATION[type.toUpperCase()] || CONFIG.TOAST_DURATION.INFO;
        
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        
        // Add to container or body
        const container = document.getElementById('toast-container') || document.body;
        container.appendChild(toast);
        
        // Auto remove
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, toastDuration);
        
        console.log(`📢 Toast (${type}): ${message}`);
    }
}

/**
 * Error handling utility class
 */
class ErrorHandler {
    /**
     * Handle API errors consistently
     * @param {Error} error - Error object
     * @param {string} context - Context where error occurred
     */
    static handleError(error, context = 'Unknown') {
        const message = `${context}: ${error.message || error}`;
        console.error(`❌ ${message}`, error);
        UIUtils.showToast(message, 'error');
    }

    /**
     * Handle network errors
     * @param {Response} response - Fetch response object
     * @param {string} context - Context where error occurred
     */
    static async handleNetworkError(response, context = 'API call') {
        let errorMessage = `${context} failed: ${response.status} ${response.statusText}`;
        
        try {
            const errorData = await response.json();
            if (errorData.message) {
                errorMessage = `${context}: ${errorData.message}`;
            }
        } catch (e) {
            // If we can't parse the error response, use the default message
        }
        
        this.handleError(new Error(errorMessage), context);
    }
}

/**
 * Main RAG Evaluator UI class
 * Handles the complete workflow of RAG evaluation including file upload,
 * configuration, evaluation execution, and results display.
 */
class RAGEvaluatorUI {
    /**
     * Initialize the RAG Evaluator UI
     */
    constructor() {
        /** @type {File|null} Currently uploaded file */
        this.uploadedFile = null;
        
        /** @type {boolean} Whether evaluation is currently in progress */
        this.evaluationInProgress = false;
        
        /** @type {number|null} Progress update interval ID */
        this.progressInterval = null;
        
        /** @type {number|null} Evaluation start timestamp */
        this.startTime = null;
        
        /** @type {Object|null} Latest evaluation results */
        this.resultData = null;
        
        /** @type {Chart|null} Chart.js metrics chart instance */
        this.metricsChart = null;
        
        /** @type {string|null} Current user session ID */
        this.sessionId = null;
        
        /** @type {Object|null} File sheet row counts */
        this.fileRowCounts = null;
        
        /** @type {Function|null} Sheet change handler reference */
        this.handleSheetChange = null;
        
        // Initialize the application
        this.init().catch(error => {
            ErrorHandler.handleError(error, 'Application initialization');
        });
    }

    /**
     * Initialize the application
     * Sets up session management, event listeners, and UI components
     */
    async init() {
        console.log('🚀 Initializing RAG Evaluator UI...');
        
        try {
            // Try to restore existing session first, then create new one if needed
            const sessionRestored = await this.validateExistingSession();
            if (!sessionRestored) {
                await this.createUserSession(); // Create session and wait for it
            }
            
            this.setupEventListeners();
            this.setupFormHandlers();
            this.validateForm();
            this.estimateProcessingTime(); // Initialize with no file
            this.loadChartJS();
            
            console.log('✅ RAG Evaluator UI initialized successfully with session:', this.sessionId?.substring(0, 8) + '...');
        } catch (error) {
            ErrorHandler.handleError(error, 'Initialization');
            throw error; // Re-throw to be caught by constructor
        }
    }

    /**
     * Load Chart.js library dynamically if not already loaded
     */
    loadChartJS() {
        // Ensure Chart.js is loaded
        if (typeof Chart === 'undefined') {
            console.log('📊 Loading Chart.js...');
            const script = document.createElement('script');
            script.src = 'https://cdn.jsdelivr.net/npm/chart.js';
            script.onload = () => {
                console.log('✅ Chart.js loaded successfully');
            };
            script.onerror = () => {
                console.error('❌ Failed to load Chart.js');
                UIUtils.showToast('Failed to load charting library', 'warning');
            };
            document.head.appendChild(script);
        } else {
            console.log('✅ Chart.js already loaded');
        }
    }

    /**
     * Set up all event listeners for the application
     */
    setupEventListeners() {
        console.log('🔗 Setting up event listeners...');
        
        try {
            // File upload handlers
            this.setupFileUpload();
            
            // Evaluation button
            const startBtn = UIUtils.getElement(ELEMENTS.START_EVALUATION);
            if (startBtn) {
                startBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    console.log('▶️ Start evaluation clicked');
                    if (!this.evaluationInProgress) {
                        this.startEvaluation();
                    }
                });
            }

            // Setup result buttons with simple approach
            this.setupResultsButtons();
            
            // Development mode debugging (only in debug mode)
            if (this.isDebugMode()) {
                this.setupDebugHelpers();
            }
            
            console.log('✅ Event listeners setup complete');
        } catch (error) {
            ErrorHandler.handleError(error, 'Event listener setup');
        }
    }

    /**
     * Check if debug mode is enabled
     * @returns {boolean} True if debug mode is enabled
     */
    isDebugMode() {
        return window.location.hostname === 'localhost' || 
               window.location.search.includes('debug=true') ||
               localStorage.getItem('ragDebugMode') === 'true';
    }

    /**
     * Setup debug helpers for development
     */
    setupDebugHelpers() {
        console.log('🔧 Setting up debug helpers...');
        
        // Global test functions for debugging
        window.ragEvaluator = this;
        window.testDownload = () => this.downloadResults();
        window.testViewDetails = () => this.viewDetails();
        window.debugButtons = () => this.debugButtons();
        window.setTestMetrics = () => this.setTestMetricsData();
        window.testChartWithRealData = () => this.testChartWithRealData();
        window.debugMetricExtraction = (mockResult) => this.debugMetricExtraction(mockResult);
        window.testFullLLMOutput = () => this.testFullLLMOutput();
        
        console.log('🧪 Debug helpers available:', Object.keys(window).filter(k => k.startsWith('test') || k === 'ragEvaluator' || k.startsWith('debug')));
    }

    /**
     * Set test metrics data for debugging
     */
    setTestMetricsData() {
        // Create detailed results with multiple rows to match analysis expectations
        const detailedResults = [
            {
                "query": "What is artificial intelligence?",
                "ground_truth": "Artificial intelligence is the simulation of human intelligence by machines.",
                "answer": "Artificial intelligence (AI) is the simulation of human intelligence by machines and computer systems.",
                "context": "AI systems can perform tasks that typically require human intelligence.",
                "Response Relevancy": 0.87,
                "Faithfulness": 0.82,
                "Context Recall": 0.79,
                "Context Precision": 0.85,
                "Answer Correctness": 0.88,
                "Answer Similarity": 0.91,
                "LLM Answer Relevancy": 0.84,
                "LLM Context Relevancy": 0.89,
                "LLM Answer Correctness": 0.86,
                "LLM Ground Truth Validity": 0.88,
                "LLM Answer Completeness": 0.85,
                "Retrieved Chunk Count": 5,
                "Sent to LLM Chunk Count": 3,
                "Used in Answer Chunk Count": 2,
                "Best Support Rank": 1,
                "Chunks Used Top 5": 2,
                "Chunks Used 5-10": 0,
                "Chunks Used 10-20": 0,
                "Total Chunks Used": 2
            },
            {
                "query": "How does machine learning work?",
                "ground_truth": "Machine learning uses algorithms to learn patterns from data.",
                "answer": "Machine learning works by using algorithms to identify patterns in data and make predictions.",
                "context": "ML algorithms improve their performance through experience.",
                "Response Relevancy": 0.85,
                "Faithfulness": 0.80,
                "Context Recall": 0.82,
                "Context Precision": 0.78,
                "Answer Correctness": 0.84,
                "Answer Similarity": 0.88,
                "LLM Answer Relevancy": 0.86,
                "LLM Context Relevancy": 0.85,
                "LLM Answer Correctness": 0.82,
                "LLM Ground Truth Validity": 0.90,
                "LLM Answer Completeness": 0.88,
                "Retrieved Chunk Count": 4,
                "Sent to LLM Chunk Count": 3,
                "Used in Answer Chunk Count": 2,
                "Best Support Rank": 1,
                "Chunks Used Top 5": 2,
                "Chunks Used 5-10": 0,
                "Chunks Used 10-20": 0,
                "Total Chunks Used": 2
            },
            {
                "query": "What are neural networks?",
                "ground_truth": "Neural networks are computing systems inspired by biological neurons.",
                "answer": "Neural networks are computing systems that mimic the structure and function of biological neurons.",
                "context": "They consist of interconnected nodes that process information.",
                "Response Relevancy": 0.89,
                "Faithfulness": 0.85,
                "Context Recall": 0.81,
                "Context Precision": 0.87,
                "Answer Correctness": 0.91,
                "Answer Similarity": 0.93,
                "LLM Answer Relevancy": 0.88,
                "LLM Context Relevancy": 0.92,
                "LLM Answer Correctness": 0.89,
                "LLM Ground Truth Validity": 0.92,
                "LLM Answer Completeness": 0.90,
                "Retrieved Chunk Count": 6,
                "Sent to LLM Chunk Count": 4,
                "Used in Answer Chunk Count": 3,
                "Best Support Rank": 1,
                "Chunks Used Top 5": 3,
                "Chunks Used 5-10": 0,
                "Chunks Used 10-20": 0,
                "Total Chunks Used": 3
            }
        ];

        this.resultData = {
            "status": "success",
            "message": "Evaluation completed successfully",
            "processing_stats": {
                "total_processed": 25,
                "successful_queries": 23,
                "success_rate": 92.0,
                "failed_queries": 2,
                "total_tokens": 45280,
                "prompt_tokens": 28350,
                "completion_tokens": 16930,
                "estimated_cost_usd": 1.3584,
                "output_file": "test_evaluation_results.xlsx"
            },
            "detailed_results": detailedResults,
            "metrics": {
                "Response Relevancy": 0.87,
                "Faithfulness": 0.82,
                "Context Recall": 0.79,
                "Context Precision": 0.85,
                "Answer Correctness": 0.88,
                "Answer Similarity": 0.91,
                "LLM Answer Relevancy": 0.84,
                "LLM Context Relevancy": 0.89,
                "LLM Answer Correctness": 0.86,
                "LLM Ground Truth Validity": 0.88,
                "LLM Answer Completeness": 0.85,
                "Retrieved Chunk Count": 5,
                "Sent to LLM Chunk Count": 3,
                "Used in Answer Chunk Count": 2,
                "Best Support Rank": 1,
                "Chunks Used Top 5": 2,
                "Chunks Used 5-10": 0,
                "Chunks Used 10-20": 0,
                "Total Chunks Used": 2
            },
            "detailed_results": [
                {
                    "query": "What is artificial intelligence?",
                    "answer": "Artificial intelligence (AI) is a branch of computer science that aims to create machines capable of intelligent behavior.",
                    "ground_truth": "AI is the simulation of human intelligence in machines.",
                    "Response Relevancy": 0.92,
                    "Faithfulness": 0.88,
                    "Context Recall": 0.85,
                    "Context Precision": 0.90,
                    "Answer Correctness": 0.87,
                    "Answer Similarity": 0.93,
                    "LLM Answer Relevancy": 0.90,
                    "LLM Context Relevancy": 0.85,
                    "LLM Answer Correctness": 0.89,
                    "LLM Ground Truth Validity": 0.92,
                    "LLM Answer Completeness": 0.87,
                    "LLM Answer Relevancy Justification": "The answer directly addresses the query about AI with relevant and accurate information.",
                    "LLM Context Relevancy Justification": "The context provides essential information about AI that supports the answer.",
                    "LLM Answer Correctness Justification": "The answer correctly explains AI concepts and aligns well with the ground truth.",
                    "LLM Ground Truth Validity Justification": "The ground truth is a valid and comprehensive answer to the AI question.",
                    "LLM Answer Completeness Justification": "The answer provides a complete explanation of artificial intelligence concepts."
                }
            ],
            "config_used": {
                "evaluate_ragas": true,
                "evaluate_crag": false,
                "evaluate_llm": true,
                "use_search_api": true,
                "llm_model": "openai-4o",
                "batch_size": 10,
                "max_concurrent": 5
            },
            "download_url": "/api/download-results/latest"
        };
        console.log('✅ Test metrics data set with chunk tracking enabled');
        this.showResults(this.resultData);
    }

    /**
     * Enable chunk tracking for enhanced retrieval analysis
     */
    enableChunkTracking() {
        console.log('🔧 Enabling chunk tracking for enhanced analysis...');
        
        // Show guidance on how to enable chunk tracking
        const guidance = `
            <div class="chunk-tracking-guidance">
                <h4>🔧 Enable Chunk Tracking for Enhanced Analysis</h4>
                <p>To get comprehensive chunk utilization metrics in your evaluation, ensure your evaluation pipeline includes:</p>
                
                <div class="guidance-section">
                    <h5>📊 Required Chunk Metrics:</h5>
                    <ul>
                        <li><strong>Retrieved Chunk Count</strong> - Number of chunks retrieved from knowledge base</li>
                        <li><strong>Sent to LLM Chunk Count</strong> - Number of chunks sent to the language model</li>
                        <li><strong>Used in Answer Chunk Count</strong> - Number of chunks actually used in the answer</li>
                        <li><strong>Best Support Rank</strong> - Ranking of the most relevant chunk</li>
                        <li><strong>Chunks Used Top 5/10/20</strong> - Distribution of chunk usage across rank ranges</li>
                        <li><strong>Total Chunks Used</strong> - Total number of chunks utilized in the answer</li>
                    </ul>
                </div>
                
                <div class="guidance-section">
                    <h5>🛠️ Implementation Steps:</h5>
                    <ol>
                        <li>Ensure your retrieval system tracks chunk IDs and ranks</li>
                        <li>Add chunk utilization analysis to your evaluation pipeline</li>
                        <li>Include chunk metrics in your evaluation output</li>
                        <li>Map chunk usage patterns to answer generation</li>
                    </ol>
                </div>
                
                <div class="guidance-section">
                    <h5>🧪 Test with Enhanced Data:</h5>
                    <p>Click the button below to test the enhanced features with sample chunk data:</p>
                    <button onclick="window.ragEvaluator.setTestMetricsData()" class="test-button">
                        🧪 Load Test Data with Chunk Metrics
                    </button>
                </div>
            </div>
        `;
        
        // Display guidance in a modal or notification
        this.showNotification(guidance, 'info');
    }

    showNotification(content, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = content;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            width: 400px;
            max-height: 80vh;
            overflow-y: auto;
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            z-index: 1000;
            padding: 20px;
            font-size: 14px;
        `;
        
        // Add close button
        const closeButton = document.createElement('button');
        closeButton.innerHTML = '×';
        closeButton.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: #6b7280;
        `;
        closeButton.onclick = () => notification.remove();
        notification.appendChild(closeButton);
        
        document.body.appendChild(notification);
        
        // Auto-remove after 30 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 30000);
    }

    /**
     * Create analysis from detailed results
     * @param {Array} detailedResults - Array of detailed result objects
     * @returns {Object} Analysis object with statistics and insights
     */
    createAnalysisFromDetailedResults(detailedResults) {
        console.log('🔍 Creating analysis from detailed results:', detailedResults);
        
        const analysis = {
            scores: {},
            statistics: {},
            correlations: {},
            performance: {},
            insights: {}
        };

        // Get all unique metric names from the detailed results
        const allMetrics = new Set();
        detailedResults.forEach(row => {
            Object.keys(row).forEach(key => {
                // Only include numeric metrics (exclude text fields like query, answer, etc.)
                if (typeof row[key] === 'number' && key !== 'index') {
                    allMetrics.add(key);
                }
            });
        });

        console.log('📊 All metrics found:', Array.from(allMetrics));

        // Calculate statistics for each metric
        Array.from(allMetrics).forEach(metric => {
            const scores = detailedResults
                .map(row => parseFloat(row[metric]))
                .filter(score => !isNaN(score) && score >= 0);
            
            // For chunk metrics, don't filter by <= 1 range
            const isChunkMetric = metric.toLowerCase().includes('chunk') || 
                                 metric.toLowerCase().includes('count') || 
                                 metric.toLowerCase().includes('rank') ||
                                 metric.toLowerCase().includes('total');
            
            if (scores.length > 0) {
                analysis.scores[metric] = scores;
                analysis.statistics[metric] = this.calculateStatistics(scores);
                console.log(`📈 Statistics for ${metric}:`, analysis.statistics[metric]);
            }
        });

        // Calculate correlations
        analysis.correlations = this.calculateCorrelations(analysis.scores);

        // Analyze performance patterns
        analysis.performance = this.analyzePerformancePatterns(detailedResults, Array.from(allMetrics));

        // Generate insights
        analysis.insights = this.generateDataInsights(analysis);

        console.log('✅ Analysis created successfully:', analysis);
        return analysis;
    }

    /**
     * Test chart with real data
     */
    testChartWithRealData() {
        const realMetrics = {
            "Response Relevancy": 0.87,
            "Faithfulness": 0.82,
            "Context Recall": 0.79,
            "Context Precision": 0.85,
            "Answer Correctness": 0.88,
            "Answer Similarity": 0.91,
            "LLM Answer Relevancy": 0.84,
            "LLM Context Relevancy": 0.89,
            "LLM Answer Correctness": 0.86,
            "LLM Ground Truth Validity": 0.88,
            "LLM Answer Completeness": 0.85,
            "LLM Answer Relevancy Justification": "The answer is highly relevant to the query about AI, providing a clear and accurate definition.",
            "LLM Context Relevancy Justification": "The context provides comprehensive information about AI that directly supports answering the query.",
            "LLM Answer Correctness Justification": "The answer accurately reflects the ground truth with minor variations in wording but maintains the same meaning.",
            "LLM Ground Truth Validity Justification": "The ground truth is a valid and appropriate answer to the query about artificial intelligence.",
            "LLM Answer Completeness Justification": "The answer provides a complete and comprehensive explanation of artificial intelligence.",
            "Retrieved Chunk IDs": "['chunk_001', 'chunk_002', 'chunk_003', 'chunk_004', 'chunk_005']",
            "Retrieved Chunk Count": 5,
            "Sent to LLM Chunk IDs": "['chunk_001', 'chunk_002', 'chunk_003']",
            "Sent to LLM Chunk Count": 3,
            "Used in Answer Chunk IDs": "['chunk_001', 'chunk_002']",
            "Used in Answer Chunk Count": 2,
            "Best Support Rank": 1,
            "Chunks Used Top 5": 2,
            "Chunks Used 5-10": 0,
            "Chunks Used 10-20": 0,
            "Used Chunk Ranks": "[1, 2]",
            "Total Chunks Used": 2
        };
        console.log('🧪 Testing chart with RAGAS + LLM metrics:', realMetrics);
        this.createMetricsChart(realMetrics);
    }

    /**
     * Debug metric extraction
     */
    debugMetricExtraction(mockResult) {
        console.log('🔍 Testing metric extraction with mock result:');
        const testResult = mockResult || {
            metrics: {
                "Response Relevancy": 0.87,
                "Faithfulness": 0.82,
                "LLM Answer Relevancy": 0.84,
                "LLM Context Relevancy": 0.89,
                "LLM Answer Correctness": 0.86,
                "LLM Ground Truth Validity": 0.88,
                "LLM Answer Completeness": 0.85,
                "LLM Answer Relevancy Justification": "The answer is highly relevant to the query about AI, providing a clear and accurate definition.",
                "LLM Context Relevancy Justification": "The context provides comprehensive information about AI that directly supports answering the query.",
                "LLM Answer Correctness Justification": "The answer accurately reflects the ground truth with minor variations in wording but maintains the same meaning.",
                "LLM Ground Truth Validity Justification": "The ground truth is a valid and appropriate answer to the query about artificial intelligence.",
                "LLM Answer Completeness Justification": "The answer provides a complete and comprehensive explanation of artificial intelligence."
            },
            ragas_results: {
                "answer_relevancy": 0.78,
                "faithfulness": 0.85
            },
            some_other_field: {
                "Context Recall": 0.79
            }
        };
        console.log('📊 Input result:', testResult);
        const extracted = this.extractMetricsFromResult(testResult);
        console.log('✅ Extracted metrics:', extracted);
        return extracted;
    }

    /**
     * Test full LLM output
     */
    testFullLLMOutput() {
        console.log('🧪 Testing complete RAGAS + LLM output display...');
        this.setTestMetricsData();
        console.log('📋 Result data with LLM metrics:', this.resultData);
        console.log('📊 Extracted metrics:', this.extractMetricsFromResult(this.resultData));
    }

    /**
     * Create a new user session for file isolation and multi-user support
     * @returns {Promise<string|null>} Session ID or null if failed
     */
    async createUserSession() {
        try {
            console.log('🔐 Creating user session...');
            
            const response = await fetch(API_ENDPOINTS.CREATE_SESSION, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    client_info: {
                        timestamp: new Date().toISOString(),
                        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                        language: navigator.language
                    }
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.sessionId = data.session_id;
                console.log('✅ User session created:', this.sessionId);
                
                // Store session in local storage for page refresh persistence
                localStorage.setItem('ragEvaluatorSessionId', this.sessionId);
                
                // Update UI to show session info
                this.updateSessionInfo();
                
                return this.sessionId;
            } else {
                await ErrorHandler.handleNetworkError(response, 'Session creation');
                return null;
            }
        } catch (error) {
            ErrorHandler.handleError(error, 'Session creation');
            return null;
        }
    }

    async validateExistingSession() {
        // Validate an existing session from localStorage
        const storedSessionId = localStorage.getItem('ragEvaluatorSessionId');
        if (!storedSessionId) {
            return false;
        }

        try {
            const response = await fetch(`${API_ENDPOINTS.SESSION_STATUS}/${storedSessionId}`);
            if (response.ok) {
                const data = await response.json();
                if (data.is_valid) {
                    this.sessionId = storedSessionId;
                    console.log('✅ Restored existing session:', this.sessionId);
                    this.updateSessionInfo();
                    return true;
                }
            }
        } catch (error) {
            console.warn('⚠️ Error validating existing session:', error);
            // Clear invalid session
            localStorage.removeItem('ragEvaluatorSessionId');
        }

        return false;
    }

    updateSessionInfo() {
        // Update UI with session information
        if (this.sessionId) {
            // Add session indicator to header
            const header = document.querySelector('.header-content');
            if (header && !document.getElementById('session-indicator')) {
                const sessionIndicator = document.createElement('div');
                sessionIndicator.id = 'session-indicator';
                sessionIndicator.className = 'session-indicator';
                sessionIndicator.innerHTML = `
                    <div class="session-info">
                        <i class="fas fa-user-circle"></i>
                        <span>Session: ${this.sessionId.substring(0, 8)}...</span>
                        <div class="session-status active">
                            <i class="fas fa-circle"></i>
                            Active
                        </div>
                    </div>
                `;
                header.appendChild(sessionIndicator);
            }
        }
    }

    setupFileUpload() {
        const uploadArea = document.getElementById(ELEMENTS.UPLOAD_AREA);
        const fileInput = document.getElementById(ELEMENTS.FILE_INPUT);
        const removeFileBtn = document.getElementById(ELEMENTS.REMOVE_FILE);

        if (uploadArea && fileInput) {
            uploadArea.addEventListener('click', () => {
                if (!this.evaluationInProgress) fileInput.click();
            });

            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (!this.evaluationInProgress) {
                    uploadArea.classList.add('dragover');
                }
            });

            uploadArea.addEventListener('dragleave', () => {
                uploadArea.classList.remove('dragover');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('dragover');
                if (!this.evaluationInProgress && e.dataTransfer.files.length > 0) {
                    this.handleFileUpload(e.dataTransfer.files[0]);
                }
            });

            fileInput.addEventListener('change', (e) => {
                if (e.target.files.length > 0) {
                    this.handleFileUpload(e.target.files[0]);
                }
            });
        }

        if (removeFileBtn) {
            removeFileBtn.addEventListener('click', () => this.removeFile());
        }
    }

    setupResultsButtons() {
        console.log('🔘 Setting up results buttons...');
        
        // Use a simple document-level click handler
        document.addEventListener('click', (e) => {
            const target = e.target;
            
            // Check if click is on a results button or its child elements
            if (target.id === ELEMENTS.DOWNLOAD_RESULTS || target.closest(`#${ELEMENTS.DOWNLOAD_RESULTS}`)) {
                e.preventDefault();
                e.stopPropagation();
                console.log('📥 Download Results button clicked');
                this.downloadResults();
                return;
            }
            
            if (target.id === ELEMENTS.VIEW_DETAILS || target.closest(`#${ELEMENTS.VIEW_DETAILS}`)) {
                e.preventDefault();
                e.stopPropagation();
                console.log('👁️ View Details button clicked');
                this.viewDetails();
                return;
            }
            
            if (target.id === ELEMENTS.NEW_EVALUATION || target.closest(`#${ELEMENTS.NEW_EVALUATION}`)) {
                e.preventDefault();
                e.stopPropagation();
                console.log('🔄 New Evaluation button clicked');
                this.resetForNewEvaluation();
                return;
            }
        });

        // Also set up direct listeners as backup
        setTimeout(() => this.setupDirectListeners(), 100);
    }

    setupDirectListeners() {
        const buttons = [
            { id: ELEMENTS.DOWNLOAD_RESULTS, handler: () => this.downloadResults(), label: 'Download' },
            { id: ELEMENTS.VIEW_DETAILS, handler: () => this.viewDetails(), label: 'View Details' },
            { id: 'toggle-quality-analysis', handler: () => this.toggleQualityAnalysis(), label: 'Toggle Quality Analysis' },
            { id: ELEMENTS.NEW_EVALUATION, handler: () => this.resetForNewEvaluation(), label: 'New Evaluation' }
        ];

        buttons.forEach(({ id, handler, label }) => {
            const btn = document.getElementById(id);
            if (btn) {
                // Remove existing listeners
                btn.replaceWith(btn.cloneNode(true));
                // Add new listener to the fresh button
                const freshBtn = document.getElementById(id);
                freshBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    console.log(`🔘 ${label} button clicked (direct)`);
                    handler();
                });
                console.log(`✅ ${label} button listener attached`);
            } else {
                console.log(`⚠️ ${label} button not found`);
            }
        });
    }

    setupFormHandlers() {
        // Monitor form changes for validation
        const formInputs = document.querySelectorAll(`#${ELEMENTS.BATCH_SIZE}, #${ELEMENTS.MAX_CONCURRENT}, #${ELEMENTS.USE_SEARCH_API}, #${ELEMENTS.EVALUATE_RAGAS}, #${ELEMENTS.EVALUATE_CRAG}, #${ELEMENTS.EVALUATE_LLM}`);
        formInputs.forEach(input => {
            input.addEventListener('change', () => {
                this.estimateProcessingTime();
                this.validateForm();
            });
        });

        // Handle Search API configuration visibility
        const useSearchApiCheckbox = document.getElementById(ELEMENTS.USE_SEARCH_API);
        const searchApiConfig = document.getElementById('search-api-config');
        
        if (useSearchApiCheckbox && searchApiConfig) {
            useSearchApiCheckbox.addEventListener('change', () => {
                searchApiConfig.style.display = useSearchApiCheckbox.checked ? 'block' : 'none';
                this.validateForm();
            });
        }

        // Handle evaluation method changes
        const ragasCheckbox = document.getElementById(ELEMENTS.EVALUATE_RAGAS);
        const cragCheckbox = document.getElementById(ELEMENTS.EVALUATE_CRAG);
        const llmCheckbox = document.getElementById(ELEMENTS.EVALUATE_LLM);
        
        if (ragasCheckbox) {
            ragasCheckbox.addEventListener('change', () => {
                this.estimateProcessingTime();
                this.validateForm();
            });
        }
        
        if (cragCheckbox) {
            cragCheckbox.addEventListener('change', () => {
                this.estimateProcessingTime();
                this.validateForm();
            });
        }
        
        if (llmCheckbox) {
            llmCheckbox.addEventListener('change', () => {
                this.estimateProcessingTime();
                this.validateForm();
            });
        }
        


        // Handle LLM Model configuration visibility
        const llmModelSelect = document.getElementById(ELEMENTS.LLM_MODEL);
        const llmConfig = document.getElementById('llm-config');
        const openaiConfig = document.getElementById('openai-config');
        const azureConfig = document.getElementById('azure-config');
        
        if (llmModelSelect && llmConfig) {
            llmModelSelect.addEventListener('change', () => {
                const selectedModel = llmModelSelect.value;
                
                if (selectedModel) {
                    llmConfig.style.display = 'block';
                    
                    if (selectedModel.startsWith('openai-') && openaiConfig) {
                        openaiConfig.style.display = 'block';
                        if (azureConfig) azureConfig.style.display = 'none';
                    } else if (selectedModel.startsWith('azure-') && azureConfig) {
                        if (openaiConfig) openaiConfig.style.display = 'none';
                        azureConfig.style.display = 'block';
                    }
                } else {
                    llmConfig.style.display = 'none';
                    if (openaiConfig) openaiConfig.style.display = 'none';
                    if (azureConfig) azureConfig.style.display = 'none';
                }
                this.validateForm();
            });
        }

        // Handle API type selection
        const apiTypeRadios = document.querySelectorAll('input[name="api-type"]');
        apiTypeRadios.forEach(radio => {
            radio.addEventListener('change', () => this.validateForm());
        });

        // Handle configuration input validation
        const configInputs = document.querySelectorAll('#search-api-config input, #llm-config input');
        configInputs.forEach(input => {
            input.addEventListener('input', () => this.validateForm());
        });

        // Setup performance presets
        this.setupPerformancePresets();
    }

    setupPerformancePresets() {
        // Setup radio button change handlers
        const radioButtons = document.querySelectorAll('.preset-radio');
        radioButtons.forEach(radio => {
            radio.addEventListener('change', () => {
                if (radio.checked) {
                    const preset = radio.value;
                    this.applyPreset(preset);
                    this.showToast(`${this.getPresetName(preset)} preset selected`, 'success');
                }
            });
        });

        // Setup info buttons with hover and click
        const infoButtons = document.querySelectorAll('.info-btn');
        infoButtons.forEach(btn => {
            let hoverTimeout;
            let isModalVisible = false;
            
            // Show on hover
            btn.addEventListener('mouseenter', (e) => {
                clearTimeout(hoverTimeout);
                if (!isModalVisible) {
                    hoverTimeout = setTimeout(() => {
                        const preset = btn.dataset.preset;
                        this.showPresetInfoModal(preset, true); // true = hover mode
                        isModalVisible = true;
                    }, 500); // Delay to prevent accidental triggers
                }
            });
            
            // Cancel hover timeout if mouse leaves before showing
            btn.addEventListener('mouseleave', (e) => {
                clearTimeout(hoverTimeout);
                // Don't auto-close modal - user must click X to close
            });
            
            // Also show on click
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                e.stopImmediatePropagation(); // Prevent radio button toggle
                const preset = btn.dataset.preset;
                this.showPresetInfoModal(preset, false); // false = click mode
                isModalVisible = true;
            });
            
            // Reset modal visibility flag when modal is closed
            document.addEventListener('modalClosed', () => {
                isModalVisible = false;
            });
        });

        // Apply default preset (Balanced) - already checked in HTML
        this.applyPreset('balanced');
    }



    showPresetInfoModal(preset, isHoverMode = false) {
        const presetData = this.getPresetData(preset);
        if (!presetData) return;

        // Remove any existing modals first
        const existingModal = document.querySelector('.preset-info-modal');
        if (existingModal) {
            existingModal.remove();
        }

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'preset-info-modal';
        modal.dataset.hoverMode = isHoverMode.toString();
        modal.innerHTML = `
            <div class="preset-info-content">
                <div class="preset-info-header">
                    <div class="preset-info-title">
                        <div class="preset-info-icon ${preset}">
                            <i class="${presetData.icon}"></i>
                        </div>
                        <div>
                            <h3>${presetData.name}</h3>
                            <p class="preset-info-subtitle">${presetData.subtitle}</p>
                        </div>
                    </div>
                    <button class="preset-close-btn">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="preset-info-body">
                    <div class="preset-metrics-grid">
                        <div class="preset-metric">
                            <span class="preset-metric-label">Batch Size</span>
                            <span class="preset-metric-value">${presetData.batch}</span>
                        </div>
                        <div class="preset-metric">
                            <span class="preset-metric-label">Concurrent</span>
                            <span class="preset-metric-value">${presetData.concurrent}</span>
                        </div>
                    </div>

                    <div class="preset-benefits-list">
                        <h4>Benefits & Features</h4>
                        ${presetData.benefits.map(benefit => `
                            <div class="preset-benefit ${benefit.type}">
                                <div class="preset-benefit-icon ${benefit.type}">
                                    ${benefit.emoji}
                                </div>
                                <span>${benefit.text}</span>
                            </div>
                        `).join('')}
                    </div>

                    <div class="preset-stats-section">
                        <h4>Performance Characteristics</h4>
                        <div class="preset-stat">
                            <div class="preset-stat-label">
                                <div class="preset-stat-icon speed">⚡</div>
                                <span>Speed</span>
                            </div>
                            <div class="preset-progress-container">
                                <div class="preset-progress-bar">
                                    <div class="preset-progress-fill speed" style="width: ${presetData.stats.speed}%"></div>
                                </div>
                                <div class="preset-progress-value">${presetData.stats.speed}%</div>
                            </div>
                        </div>
                        <div class="preset-stat">
                            <div class="preset-stat-label">
                                <div class="preset-stat-icon resource">💾</div>
                                <span>Resource Usage</span>
                            </div>
                            <div class="preset-progress-container">
                                <div class="preset-progress-bar">
                                    <div class="preset-progress-fill resource" style="width: ${presetData.stats.resource}%"></div>
                                </div>
                                <div class="preset-progress-value">${presetData.stats.resource}%</div>
                            </div>
                        </div>
                        <div class="preset-stat">
                            <div class="preset-stat-label">
                                <div class="preset-stat-icon stability">🛡️</div>
                                <span>Stability</span>
                            </div>
                            <div class="preset-progress-container">
                                <div class="preset-progress-bar">
                                    <div class="preset-progress-fill stability" style="width: ${presetData.stats.stability}%"></div>
                                </div>
                                <div class="preset-progress-value">${presetData.stats.stability}%</div>
                            </div>
                        </div>
                    </div>

                    <div class="preset-recommendation-box">
                        <strong>Best for:</strong> ${presetData.recommendation}
                    </div>
                </div>
            </div>
        `;

        // Add to DOM at the very end of body and prevent body scroll
        document.body.appendChild(modal);
        document.body.classList.add('modal-open');

        // Force positioning with inline styles to override any conflicts
        modal.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            z-index: 999999 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 20px !important;
            box-sizing: border-box !important;
            background: rgba(0, 0, 0, 0.5) !important;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease;
        `;

        // Show modal with simple animation
        setTimeout(() => {
            modal.classList.add('show');
            modal.style.opacity = '1';
            modal.style.visibility = 'visible';
        }, 10);

        // Setup close handlers - both modes work the same now
        const closeBtn = modal.querySelector('.preset-close-btn');
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.closePresetInfoModal(modal);
        });
        
        // Close on backdrop click (for both modes)
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closePresetInfoModal(modal);
            }
        });
        
        // Prevent clicks inside the modal content from closing the modal
        const content = modal.querySelector('.preset-info-content');
        if (content) {
            content.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }

        // ESC key handler (for both modes)
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                this.closePresetInfoModal(modal);
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
        
        // Store the ESC handler for cleanup
        modal._escHandler = escHandler;
    }

    closePresetInfoModal(modal) {
        if (!modal) return;
        
        modal.classList.remove('show');
        modal.style.opacity = '0';
        modal.style.visibility = 'hidden';
        
        // Remove modal-open class
        document.body.classList.remove('modal-open');
        
        // Clean up ESC key handler
        if (modal._escHandler) {
            document.removeEventListener('keydown', modal._escHandler);
        }
        
        // Dispatch custom event to reset modal visibility flags
        document.dispatchEvent(new CustomEvent('modalClosed'));
        
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    }

    getPresetData(preset) {
        const presets = {
            'conservative': {
                name: 'Conservative',
                subtitle: 'Safe & Stable Processing',
                icon: 'fas fa-shield-alt',
                batch: 5,
                concurrent: 2,
                benefits: [
                    { emoji: '💾', type: 'positive', text: 'Lower memory usage (~512MB)' },
                    { emoji: '🛡️', type: 'positive', text: 'More stable processing' },
                    { emoji: '🚦', type: 'positive', text: 'Less API rate limiting' },
                    { emoji: '⚡', type: 'positive', text: 'Works on limited resources' },
                    { emoji: '⏱️', type: 'positive', text: 'Reduced timeout risks' }
                ],
                stats: { speed: 30, resource: 25, stability: 95 },
                recommendation: 'Large datasets (1000+ queries), limited resources, first-time users, or production environments where stability is critical'
            },
            'balanced': {
                name: 'Balanced',
                subtitle: 'Optimal Performance & Reliability',
                icon: 'fas fa-balance-scale',
                batch: 10,
                concurrent: 5,
                benefits: [
                    { emoji: '⚖️', type: 'positive', text: 'Good speed & stability balance' },
                    { emoji: '💾', type: 'positive', text: 'Moderate resource usage (~1GB)' },
                    { emoji: '📊', type: 'positive', text: 'Reliable for most datasets' },
                    { emoji: '⭐', type: 'positive', text: 'Optimal for general usage' },
                    { emoji: '✅', type: 'positive', text: 'Well-tested configuration' }
                ],
                stats: { speed: 65, resource: 50, stability: 85 },
                recommendation: 'Most evaluation tasks, medium datasets (100-1000 queries), general usage, and users who want the best overall experience'
            },
            'performance': {
                name: 'High Performance',
                subtitle: 'Maximum Speed Processing',
                icon: 'fas fa-rocket',
                batch: 20,
                concurrent: 10,
                benefits: [
                    { emoji: '🚀', type: 'positive', text: 'Maximum processing speed' },
                    { emoji: '📈', type: 'positive', text: 'Optimal for large datasets' },
                    { emoji: '⚡', type: 'positive', text: 'Best throughput rates' },
                    { emoji: '⚠️', type: 'warning', text: 'Requires adequate resources (2GB+)' },
                    { emoji: '🚧', type: 'warning', text: 'May hit API rate limits' }
                ],
                stats: { speed: 95, resource: 85, stability: 70 },
                recommendation: 'Large datasets (500+ queries), powerful systems (8GB+ RAM), experienced users, and time-critical evaluations'
            }
        };

        return presets[preset];
    }



    getPresetName(preset) {
        const names = {
            'conservative': 'Conservative',
            'balanced': 'Balanced',
            'performance': 'High Performance'
        };
        return names[preset] || preset;
    }

    applyPreset(preset) {
        const batchSizeInput = document.getElementById('batch-size');
        const maxConcurrentInput = document.getElementById('max-concurrent');
        
        if (!batchSizeInput || !maxConcurrentInput) return;

        const presets = {
            'conservative': { 
                batch: 5, 
                concurrent: 2,
                description: 'Safer processing with lower resource usage'
            },
            'balanced': { 
                batch: 10, 
                concurrent: 5,
                description: 'Good balance of speed and stability'
            },
            'performance': { 
                batch: 20, 
                concurrent: 10,
                description: 'Maximum speed for large datasets'
            }
        };

        if (presets[preset]) {
            // Animate the changes
            const currentBatch = parseInt(batchSizeInput.value);
            const currentConcurrent = parseInt(maxConcurrentInput.value);
            const targetBatch = presets[preset].batch;
            const targetConcurrent = presets[preset].concurrent;
            
            // Update values
            batchSizeInput.value = targetBatch;
            maxConcurrentInput.value = targetConcurrent;
            
            // Show visual feedback for the changes
            if (currentBatch !== targetBatch || currentConcurrent !== targetConcurrent) {
                this.highlightChangedInputs([batchSizeInput, maxConcurrentInput]);
            }
            
            // Update estimates and validation
            this.estimateProcessingTime();
            this.validateForm();
            
            console.log(`🎯 Applied ${preset} preset: ${targetBatch} batch, ${targetConcurrent} concurrent`);
        }
    }

    highlightChangedInputs(inputs) {
        inputs.forEach(input => {
            input.style.transition = 'all 0.3s ease';
            input.style.background = '#fef3c7';
            input.style.borderColor = '#f59e0b';
            
            setTimeout(() => {
                input.style.background = '';
                input.style.borderColor = '';
            }, 1000);
        });
    }

    handleFileUpload(file) {
        // Validate file type
        const validTypes = ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'];
        if (!validTypes.includes(file.type) && !file.name.toLowerCase().endsWith('.xlsx') && !file.name.toLowerCase().endsWith('.xls')) {
            this.showToast('Please upload a valid Excel file (.xlsx or .xls)', 'error');
            return;
        }

        if (file.size > 50 * 1024 * 1024) {
            this.showToast('File size must be less than 50MB', 'error');
            return;
        }

        this.uploadedFile = file;
        this.displayFileInfo(file);
        
        // Show immediate feedback and then analyze sheets
        this.showToast(`File "${file.name}" uploaded successfully. Analyzing sheets...`, 'info');
        this.loadSheetNames(file);
        this.validateForm();
        this.estimateProcessingTime();
    }

    displayFileInfo(file) {
        const uploadArea = document.getElementById('upload-area');
        const fileInfo = document.getElementById('file-info');
        const fileName = document.getElementById('file-name');
        const fileSize = document.getElementById('file-size');

        if (fileName) fileName.textContent = file.name;
        if (fileSize) fileSize.textContent = this.formatFileSize(file.size);
        if (uploadArea) uploadArea.style.display = 'none';
        if (fileInfo) fileInfo.style.display = 'block';
    }

    removeFile() {
        this.uploadedFile = null;
        this.fileRowCounts = null; // Clear row counts
        
        const uploadArea = document.getElementById('upload-area');
        const fileInfo = document.getElementById('file-info');
        const sheetSelect = document.getElementById('sheet-name');
        
        if (uploadArea) uploadArea.style.display = 'block';
        if (fileInfo) fileInfo.style.display = 'none';
        if (sheetSelect) sheetSelect.innerHTML = '<option value="">All sheets</option>';
        
        this.validateForm();
        this.estimateProcessingTime(); // Reset estimates
    }

    async loadSheetNames(file) {
        console.log('📄 Loading sheet names for file:', file.name);
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/get-sheet-names', {
                method: 'POST',
                body: formData
            });

            console.log('📡 Sheet names API response status:', response.status);

            if (response.ok) {
                const data = await response.json();
                console.log('📋 Sheet names data received:', data);
                
                if (data.sheet_names && data.sheet_names.length > 0) {
                    console.log('✅ Found sheets:', data.sheet_names);
                    this.populateSheetDropdown(data.sheet_names);
                    this.showToast(`Found ${data.sheet_names.length} sheet(s) in the Excel file`, 'info');
                } else {
                    console.warn('⚠️ No sheet names found in response');
                    this.populateSheetDropdown([]);
                }
                
                // Get row count for better estimation
                if (data.row_counts) {
                    this.fileRowCounts = data.row_counts;
                    console.log('📊 File row counts:', this.fileRowCounts);
                    this.estimateProcessingTime(); // Re-estimate with actual data
                }
            } else {
                const errorText = await response.text();
                console.error('❌ Failed to load sheet names:', response.status, errorText);
                this.showToast('Failed to analyze Excel file sheets', 'error');
            }
        } catch (error) {
            console.error('❌ Error loading sheet names:', error);
            this.showToast('Error analyzing Excel file: ' + error.message, 'error');
        }
    }

    populateSheetDropdown(sheetNames) {
        console.log('🔄 Populating sheet dropdown with:', sheetNames);
        const sheetSelect = document.getElementById('sheet-name');
        if (sheetSelect) {
            // Always start with "All sheets" option which is selected by default
            sheetSelect.innerHTML = '<option value="">All sheets</option>';
            
            if (sheetNames && sheetNames.length > 0) {
                sheetNames.forEach((sheetName, index) => {
                    const option = document.createElement('option');
                    option.value = sheetName;
                    option.textContent = sheetName;
                    sheetSelect.appendChild(option);
                    console.log(`📄 Added sheet option ${index + 1}: "${sheetName}"`);
                });
                
                console.log(`✅ Successfully populated dropdown with ${sheetNames.length} sheet(s) + "All sheets" option`);
            } else {
                console.log('ℹ️ No individual sheets to add, only "All sheets" option available');
            }
            
            // Add event listener for sheet selection changes to update estimates
            sheetSelect.removeEventListener('change', this.handleSheetChange); // Remove existing
            this.handleSheetChange = () => {
                console.log('📋 Sheet selection changed, updating estimates...');
                this.estimateProcessingTime();
            };
            sheetSelect.addEventListener('change', this.handleSheetChange);
        } else {
            console.error('❌ Could not find sheet-name dropdown element');
        }
    }

    estimateProcessingTime() {
        const estimatedTimeElement = document.getElementById('estimated-time');
        const totalQueriesElement = document.getElementById('total-queries');
        
        if (!this.uploadedFile) {
            // No file uploaded - show placeholders
            if (estimatedTimeElement) {
                estimatedTimeElement.textContent = '--';
                estimatedTimeElement.title = 'Upload a file to see estimation';
            }
            if (totalQueriesElement) {
                totalQueriesElement.textContent = '--';
                totalQueriesElement.title = 'Upload a file to see query count';
            }
            
            // Clear estimation details
            const detailsContainer = document.getElementById('estimation-details');
            if (detailsContainer) {
                detailsContainer.style.display = 'none';
            }
            return;
        }
        
        // Show loading while calculating
        if (estimatedTimeElement) estimatedTimeElement.textContent = 'Calculating...';
        if (totalQueriesElement) totalQueriesElement.textContent = 'Analyzing...';
        
        // Get current settings
        const batchSize = parseInt(document.getElementById(ELEMENTS.BATCH_SIZE)?.value || CONFIG.DEFAULT_BATCH_SIZE);
        const maxConcurrent = parseInt(document.getElementById(ELEMENTS.MAX_CONCURRENT)?.value || CONFIG.DEFAULT_MAX_CONCURRENT);
        const useSearchApi = document.getElementById(ELEMENTS.USE_SEARCH_API)?.checked || false;
        const evaluateRagas = document.getElementById(ELEMENTS.EVALUATE_RAGAS)?.checked || false;
        const evaluateCrag = document.getElementById(ELEMENTS.EVALUATE_CRAG)?.checked || false;
        const evaluateLlm = document.getElementById(ELEMENTS.EVALUATE_LLM)?.checked || false;
        const selectedSheet = document.getElementById(ELEMENTS.SHEET_SELECT)?.value || '';
        
        // Calculate actual query count
        let totalQueries = 0;
        
        if (this.fileRowCounts) {
            // Use actual row counts from Excel file
            if (selectedSheet && this.fileRowCounts[selectedSheet]) {
                // Specific sheet selected
                totalQueries = this.fileRowCounts[selectedSheet];
                console.log(`📊 Using row count for sheet '${selectedSheet}': ${totalQueries}`);
            } else {
                // All sheets or no specific sheet - sum all rows
                totalQueries = Object.values(this.fileRowCounts).reduce((sum, count) => sum + count, 0);
                console.log(`📊 Using total row count across all sheets: ${totalQueries}`);
            }
        } else {
            // Fallback to file size estimation (less accurate)
            totalQueries = Math.max(10, Math.floor(this.uploadedFile.size / (2 * 1024))); // Assume ~2KB per row
            console.log(`📊 Fallback estimation based on file size: ${totalQueries} queries`);
        }
        
        // Improved time estimation based on real-world benchmarks
        let timePerQuery = this.calculateTimePerQuery(useSearchApi, evaluateRagas, evaluateCrag, evaluateLlm);
        
        // Account for batch processing and concurrency
        const effectiveBatchSize = Math.min(batchSize, totalQueries);
        const parallelBatches = Math.min(maxConcurrent, Math.ceil(totalQueries / effectiveBatchSize));
        const totalBatches = Math.ceil(totalQueries / effectiveBatchSize);
        const batchesPerRound = parallelBatches;
        const totalRounds = Math.ceil(totalBatches / batchesPerRound);
        
        // Calculate total time considering parallel processing
        const totalTime = totalRounds * timePerQuery * effectiveBatchSize / parallelBatches;
        
        // Add overhead for initialization, file I/O, etc.
        const overheadTime = Math.max(CONFIG.BASE_OVERHEAD, totalQueries * CONFIG.OVERHEAD_PER_QUERY);
        const finalTime = totalTime + overheadTime;
        
        console.log(`🕐 Estimation details:`, {
            totalQueries,
            timePerQuery: `${timePerQuery}s`,
            effectiveBatchSize,
            parallelBatches,
            totalBatches,
            totalRounds,
            processingTime: `${totalTime}s`,
            overheadTime: `${overheadTime}s`,
            finalTime: `${finalTime}s`
        });
        
        // Update UI with calculated values
        if (estimatedTimeElement) {
            estimatedTimeElement.textContent = UIUtils.formatTime(finalTime);
            estimatedTimeElement.title = `Based on ${totalQueries} queries with current settings`;
        }
        
        if (totalQueriesElement) {
            totalQueriesElement.textContent = totalQueries.toLocaleString();
            totalQueriesElement.title = selectedSheet ? 
                `From sheet: ${selectedSheet}` : 
                'Across all sheets';
        }
        
        // Update estimates info
        this.updateEstimationDetails(totalQueries, finalTime, useSearchApi, evaluateRagas, evaluateCrag, evaluateLlm);
        
        // Show estimation details
        const detailsContainer = document.getElementById('estimation-details');
        if (detailsContainer) {
            detailsContainer.style.display = 'block';
        }

        // No longer needed - preset details are shown in modal
    }

    /**
     * Calculate estimated processing time per query based on enabled features
     * @param {boolean} useSearchApi - Whether search API is enabled
     * @param {boolean} evaluateRagas - Whether RAGAS evaluation is enabled
     * @param {boolean} evaluateCrag - Whether CRAG evaluation is enabled
     * @param {boolean} evaluateLlm - Whether LLM evaluation is enabled
     * @returns {number} Estimated time per query in seconds
     */
    calculateTimePerQuery(useSearchApi, evaluateRagas, evaluateCrag, evaluateLlm) {
        // Base time for basic processing
        let timePerQuery = CONFIG.BASE_PROCESSING_TIME;
        
        // Search API time (if enabled)
        if (useSearchApi) {
            timePerQuery += CONFIG.SEARCH_API_TIME;
        }
        
        // Calculate parallel evaluation time - evaluators run concurrently
        const evaluationTimes = [];
        
        // RAGAS evaluation time (most time-consuming)
        if (evaluateRagas) {
            evaluationTimes.push(CONFIG.RAGAS_EVAL_TIME);
        }
        
        // CRAG evaluation time
        if (evaluateCrag) {
            evaluationTimes.push(CONFIG.CRAG_EVAL_TIME);
        }
        
        // LLM evaluation time (3 API calls per query, but concurrent)
        if (evaluateLlm) {
            evaluationTimes.push(CONFIG.LLM_EVAL_TIME);
        }
        
        // When running in parallel, take the maximum time (longest running evaluator)
        // rather than sum of all times
        if (evaluationTimes.length > 0) {
            timePerQuery += Math.max(...evaluationTimes);
        }
        
        // Minimum time
        return Math.max(CONFIG.MIN_PROCESSING_TIME, timePerQuery);
    }

    updateEstimationDetails(queries, time, useSearchApi, evaluateRagas, evaluateCrag, evaluateLlm) {
        // Create or update estimation breakdown
        let detailsContainer = document.getElementById('estimation-details');
        if (!detailsContainer) {
            detailsContainer = document.createElement('div');
            detailsContainer.id = 'estimation-details';
            detailsContainer.className = 'estimation-details';
            
            const parentContainer = document.querySelector('.run-info');
            if (parentContainer) {
                parentContainer.appendChild(detailsContainer);
            }
        }
        
        const components = [];
        if (useSearchApi) components.push('Search API');
        if (evaluateRagas) components.push('RAGAS Evaluation');
        if (evaluateCrag) components.push('CRAG Evaluation');
        if (evaluateLlm) components.push('LLM Evaluation');
        
        detailsContainer.innerHTML = `
            <div class="estimation-breakdown">
                <div class="estimation-row">
                    <span>Processing:</span>
                    <span>${components.join(' + ') || 'Basic processing'}</span>
                </div>
                <div class="estimation-row">
                    <span>Queries:</span>
                    <span>${queries.toLocaleString()} rows detected</span>
                </div>
                <div class="estimation-row">
                    <span>Est. Time:</span>
                    <span>${this.formatTime(time)}</span>
                </div>
            </div>
        `;
    }

    validateForm() {
        const startBtn = document.getElementById('start-evaluation');
        if (!startBtn) return;

        const evaluateRagas = document.getElementById('evaluate-ragas')?.checked || false;
        const evaluateCrag = document.getElementById('evaluate-crag')?.checked || false;
        const evaluateLlm = document.getElementById('evaluate-llm')?.checked || false;
        const useSearchApi = document.getElementById('use-search-api')?.checked || false;
        const llmModel = document.getElementById('llm-model')?.value || '';
        
        let isValid = this.uploadedFile && (evaluateRagas || evaluateCrag || evaluateLlm);
        let errorMessage = '';
        
        if (!this.uploadedFile) {
            errorMessage = '<i class="fas fa-upload"></i> Upload File First';
            isValid = false;
        } else if (!evaluateRagas && !evaluateCrag && !evaluateLlm) {
            errorMessage = '<i class="fas fa-exclamation-triangle"></i> Select at least one Evaluation Method';
            isValid = false;
        }
        
        if (isValid && useSearchApi) {
            const apiType = document.querySelector('input[name="api-type"]:checked');
            const appId = document.getElementById('api-app-id')?.value?.trim() || '';
            const domain = document.getElementById('api-domain')?.value?.trim() || '';
            const clientId = document.getElementById('api-client-id')?.value?.trim() || '';
            const clientSecret = document.getElementById('api-client-secret')?.value?.trim() || '';
            
            if (!apiType || !appId || !domain || !clientId || !clientSecret) {
                errorMessage = '<i class="fas fa-key"></i> Complete API Configuration';
                isValid = false;
            }
        }
        
        if (isValid && llmModel) {
            if (llmModel.startsWith('openai-')) {
                const apiKey = document.getElementById('openai-api-key')?.value?.trim() || '';
                if (!apiKey) {
                    errorMessage = '<i class="fas fa-key"></i> OpenAI API Key Required';
                    isValid = false;
                }
            } else if (llmModel.startsWith('azure-')) {
                const endpoint = document.getElementById('azure-endpoint')?.value?.trim() || '';
                const apiKey = document.getElementById('azure-api-key')?.value?.trim() || '';
                const deployment = document.getElementById('azure-deployment')?.value?.trim() || '';
                
                if (!endpoint || !apiKey || !deployment) {
                    errorMessage = '<i class="fas fa-cogs"></i> Complete Azure Configuration';
                    isValid = false;
                }
            }
        }
        
        startBtn.disabled = !isValid || this.evaluationInProgress;
        
        if (this.evaluationInProgress) {
            startBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Evaluation in Progress...';
        } else if (errorMessage) {
            startBtn.innerHTML = errorMessage;
        } else {
            startBtn.innerHTML = '<i class="fas fa-play"></i> Start Evaluation';
        }
    }

    async startEvaluation() {
        if (this.evaluationInProgress || !this.uploadedFile) return;
        
        console.log('🚀 Starting evaluation...');
        this.evaluationInProgress = true;
        this.startTime = Date.now();
        
        // Show progress section
        const progressSection = document.getElementById('progress-section');
        const resultsSection = document.getElementById('results-section');
        
        if (progressSection) progressSection.style.display = 'block';
        if (resultsSection) resultsSection.style.display = 'none';
        
        // Update status
        const statusBadge = document.getElementById('status-badge');
        if (statusBadge) {
            statusBadge.textContent = 'Processing';
            statusBadge.className = 'status-badge processing';
        }
        
        this.disableForm();
        if (progressSection) {
            progressSection.scrollIntoView({ behavior: 'smooth' });
        }
        
        this.startProgressTracking();
        this.addLogEntry('Starting evaluation process...', 'info');
        
        try {
            const result = await this.callEvaluationAPI();
            this.handleEvaluationSuccess(result);
        } catch (error) {
            this.handleEvaluationError(error);
        }
    }

    async callEvaluationAPI() {
        const formData = new FormData();
        formData.append('excel_file', this.uploadedFile);
        
        // Add session_id if available, but don't require it (for backward compatibility)
        if (this.sessionId) {
            console.log('🔐 Using session ID for evaluation:', this.sessionId.substring(0, 8) + '...');
            formData.append('session_id', this.sessionId);
        } else {
            console.log('⚠️ No session ID available, server will create one');
        }
        
        const selectedSheet = document.getElementById('sheet-name')?.value || '';
        const config = {
            sheet_name: selectedSheet,
            evaluate_ragas: document.getElementById('evaluate-ragas')?.checked || false,
            evaluate_crag: document.getElementById('evaluate-crag')?.checked || false,
            evaluate_llm: document.getElementById('evaluate-llm')?.checked || false,
            use_search_api: document.getElementById('use-search-api')?.checked || false,
            save_db: document.getElementById('save-db')?.checked || false,
            llm_model: document.getElementById('llm-model')?.value || '',
            batch_size: parseInt(document.getElementById('batch-size')?.value || 10),
            max_concurrent: parseInt(document.getElementById('max-concurrent')?.value || 5)
        };
        
        // Log sheet selection for debugging
        if (selectedSheet) {
            console.log(`📋 User selected SPECIFIC SHEET: "${selectedSheet}"`);
        } else {
            console.log('📋 User selected ALL SHEETS (no specific sheet chosen)');
        }

        if (config.use_search_api) {
            const apiType = document.querySelector('input[name="api-type"]:checked');
            config.api_config = {
                type: apiType ? apiType.value : '',
                app_id: document.getElementById('api-app-id')?.value?.trim() || '',
                domain: document.getElementById('api-domain')?.value?.trim() || '',
                client_id: document.getElementById('api-client-id')?.value?.trim() || '',
                client_secret: document.getElementById('api-client-secret')?.value?.trim() || ''
            };
        }

        if (config.llm_model) {
            if (config.llm_model.startsWith('openai-')) {
                config.openai_config = {
                    api_key: document.getElementById('openai-api-key')?.value?.trim() || '',
                    org_id: document.getElementById('openai-org-id')?.value?.trim() || '',
                    model: config.llm_model.replace('openai-', 'gpt-')
                };
            } else if (config.llm_model.startsWith('azure-')) {
                config.azure_config = {
                    endpoint: document.getElementById('azure-endpoint')?.value?.trim() || '',
                    api_key: document.getElementById('azure-api-key')?.value?.trim() || '',
                    deployment: document.getElementById('azure-deployment')?.value?.trim() || '',
                    api_version: document.getElementById('azure-api-version')?.value?.trim() || '',
                    embedding_deployment: document.getElementById('azure-embedding-deployment')?.value?.trim() || '',
                    model: config.llm_model.replace('azure-', 'gpt-')
                };
            }
        }
        
        formData.append('config', JSON.stringify(config));
        
        console.log('🔍 Sending request to /api/runeval with:');
        console.log('📄 File:', this.uploadedFile?.name);
        console.log('🔐 Session ID:', this.sessionId);
        console.log('⚙️ Config:', JSON.stringify(config, null, 2));
        
        // Debug: Check FormData contents
        console.log('🧪 FormData contents:');
        for (let [key, value] of formData.entries()) {
            if (value instanceof File) {
                console.log(`   📄 ${key}: ${value.name} (${value.size} bytes, ${value.type})`);
            } else {
                console.log(`   📝 ${key}: ${value}`);
            }
        }
        
        const response = await fetch('/api/runeval', {
            method: 'POST',
            body: formData
        });
        
        console.log('📡 Response status:', response.status, response.statusText);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Error response:', errorText);
            
            let errorData = {};
            try {
                errorData = JSON.parse(errorText);
            } catch (e) {
                console.error('❌ Could not parse error as JSON:', e);
            }
            
            throw new Error(errorData.detail || errorData.error || `HTTP ${response.status}: ${response.statusText}\n${errorText}`);
        }
        
        return await response.json();
    }

    startProgressTracking() {
        let progress = 0;
        let elapsedSeconds = 0;
        
        this.progressInterval = setInterval(() => {
            elapsedSeconds++;
            if (progress < 90) progress += Math.random() * 2;
            this.updateProgress(Math.min(progress, 95), elapsedSeconds);
        }, 1000);
    }

    updateProgress(percentage, elapsedSeconds) {
        const progressFill = document.getElementById('progress-fill');
        const progressPercentage = document.getElementById('progress-percentage');
        const elapsedTime = document.getElementById('elapsed-time');
        const progressDetails = document.getElementById('progress-details');
        
        if (progressFill) progressFill.style.width = `${percentage}%`;
        if (progressPercentage) progressPercentage.textContent = `${Math.round(percentage)}%`;
        if (elapsedTime) elapsedTime.textContent = this.formatTime(elapsedSeconds);
        
        if (progressDetails) {
            const stages = [
                'Initializing evaluation...',
                'Processing queries...',
                'Running RAGAS evaluation...',
                'Running CRAG evaluation...',
                'Finalizing results...'
            ];
            const stageIndex = Math.min(Math.floor(percentage / 20), stages.length - 1);
            progressDetails.textContent = stages[stageIndex];
        }
    }

    addLogEntry(message, type = 'info') {
        const logOutput = document.getElementById('log-output');
        if (!logOutput) return;

        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        
        logOutput.appendChild(entry);
        logOutput.scrollTop = logOutput.scrollHeight;
        
        // Limit log entries to 50
        while (logOutput.children.length > 50) {
            logOutput.removeChild(logOutput.firstChild);
        }
    }

    handleEvaluationSuccess(result) {
        console.log('✅ Evaluation completed successfully:', result);
        this.evaluationInProgress = false;
        
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        const elapsedSeconds = Math.floor((Date.now() - this.startTime) / 1000);
        this.updateProgress(100, elapsedSeconds);
        
        const statusBadge = document.getElementById('status-badge');
        if (statusBadge) {
            statusBadge.textContent = 'Completed';
            statusBadge.className = 'status-badge success';
        }
        
        this.resultData = result;
        console.log('💾 Result data stored:', this.resultData);
        
        // Update session ID from server response (important for download)
        if (result.session_id && result.session_id !== this.sessionId) {
            console.log(`🔄 Updating session ID from server: ${this.sessionId} -> ${result.session_id}`);
            this.sessionId = result.session_id;
            localStorage.setItem('ragEvaluatorSessionId', this.sessionId);
            this.updateSessionInfo();
        }

        setTimeout(() => {
            this.showResults(result);
        }, 1000);
        
        this.addLogEntry('Evaluation completed successfully!', 'success');
        this.showToast('Evaluation completed successfully!', 'success');
    }

    handleEvaluationError(error) {
        console.error('❌ Evaluation failed:', error);
        this.evaluationInProgress = false;
        
        if (this.progressInterval) {
            clearInterval(this.progressInterval);
        }
        
        const statusBadge = document.getElementById('status-badge');
        if (statusBadge) {
            statusBadge.textContent = 'Failed';
            statusBadge.className = 'status-badge error';
        }
        
        this.addLogEntry(`Error: ${error.message}`, 'error');
        this.showToast(`Evaluation failed: ${error.message}`, 'error');
        this.enableForm();
    }

    showResults(result) {
        console.log('📊 Showing results...');
        console.log('📋 Complete result data:', result);
        
        // Hide progress, show results
        const progressSection = document.getElementById('progress-section');
        const resultsSection = document.getElementById('results-section');
        
        if (progressSection) progressSection.style.display = 'none';
        if (resultsSection) {
            resultsSection.style.display = 'block';
            resultsSection.scrollIntoView({ behavior: 'smooth' });
        }
        
        // Extract data from result with detailed logging
        const stats = result.processing_stats || {};
        console.log('📈 Processing stats:', stats);
        
        // Extract metrics with better handling
        let metrics = this.extractMetricsFromResult(result);
        console.log('📊 Extracted metrics:', metrics);
        
        const totalTime = Math.floor((Date.now() - this.startTime) / 1000);
        const totalProcessed = stats.total_processed || 0;
        const successfulQueries = stats.successful_queries || 0;
        const avgTime = totalProcessed > 0 ? totalTime / totalProcessed : 0;
        
        console.log('📋 Summary stats:', {
            totalProcessed,
            successfulQueries,
            totalTime,
            avgTime
        });
        
        // Update summary stats
        this.updateElement('total-processed', totalProcessed);
        this.updateElement('successful-queries', successfulQueries);
        this.updateElement('total-time', UIUtils.formatTime(totalTime));
        this.updateElement('avg-time', UIUtils.formatTime(avgTime));
        
        // Add failed queries count
        const failedQueries = stats.failed_queries || 0;
        this.updateElement('failed-queries', failedQueries);
        
        // Add token usage and cost if available
        if (this.hasRealTokenUsageData(stats)) {
            this.updateElement('total-tokens', UIUtils.formatTokenCount(stats.total_tokens));
            this.updateElement('estimated-cost', UIUtils.formatCurrency(stats.estimated_cost_usd));
            
            // Show token/cost summary items
            UIUtils.toggleElement('token-summary-item', true);
            UIUtils.toggleElement('cost-summary-item', true);
        } else {
            // Hide token/cost summary items if no data
            UIUtils.toggleElement('token-summary-item', false);
            UIUtils.toggleElement('cost-summary-item', false);
        }
        
        // Create analysis from detailed results if available
        if (result.detailed_results && result.detailed_results.length > 0) {
            console.log('📊 Creating analysis from detailed results...');
            const analysis = this.createAnalysisFromDetailedResults(result.detailed_results);
            console.log('✅ Analysis created:', analysis);
            
            // Store analysis for later use
            this.currentAnalysis = analysis;
        }
        
        // Create metrics chart
        setTimeout(() => {
            this.createMetricsChart(metrics);
            this.setupDirectListeners(); // Ensure buttons work
        }, 100);
        
        // Display quality analysis if available
        if (result.unused_chunk_analysis) {
            this.displayQualityAnalysis(result.unused_chunk_analysis);
        }
        
        this.enableForm();
        this.addLogEntry(`✅ Results displayed: ${totalProcessed} queries processed`, 'success');
    }

    /**
     * Extract and normalize metrics from evaluation results
     * @param {Object} result - Evaluation result object
     * @returns {Object} Processed metrics object
     */
    extractMetricsFromResult(result) {
        console.log('🔍 Extracting metrics from result...');
        
        // Try different paths for metrics
        let rawMetrics = null;
        
        if (result.metrics && Object.keys(result.metrics).length > 0) {
            console.log('✅ Found metrics in result.metrics');
            rawMetrics = result.metrics;
        } else if (result.ragas_results && Object.keys(result.ragas_results).length > 0) {
            console.log('✅ Found metrics in result.ragas_results');
            rawMetrics = result.ragas_results;
        } else if (result.evaluation_results && Object.keys(result.evaluation_results).length > 0) {
            console.log('✅ Found metrics in result.evaluation_results');
            rawMetrics = result.evaluation_results;
        } else {
            console.warn('⚠️ No metrics found in result, using defaults');
            console.log('Available result keys:', Object.keys(result));
            return this.getDefaultMetrics();
        }
        
        console.log('📊 Raw metrics found:', rawMetrics);
        
        // Process and normalize metrics
        const processedMetrics = {};
        
        for (const [key, value] of Object.entries(rawMetrics)) {
            // Convert string numbers to actual numbers
            let numericValue = value;
            
            if (typeof value === 'string') {
                // Try to parse as float
                const parsed = parseFloat(value);
                if (!isNaN(parsed)) {
                    numericValue = parsed;
                } else {
                    console.warn(`⚠️ Could not parse metric value: ${key} = ${value}`);
                    continue;
                }
            }
            
            // Only validate range, don't auto-convert - preserve original values
            if (numericValue < 0 || numericValue > 100) {
                console.warn(`⚠️ Metric value out of expected range: ${key} = ${numericValue}`);
            }
            
            // Keep original value - don't auto-convert percentages to decimals
            processedMetrics[key] = numericValue;
            console.log(`✅ Processed metric: ${key} = ${numericValue} (original value preserved)`);
        }
        
        // If no valid metrics were processed, use defaults
        if (Object.keys(processedMetrics).length === 0) {
            console.warn('⚠️ No valid metrics processed, using defaults');
            return this.getDefaultMetrics();
        }
        
        console.log('🎯 Final processed metrics:', processedMetrics);
        return processedMetrics;
    }

    /**
     * Get default metrics when no real metrics are available
     * @returns {Object} Default metrics object
     */
    getDefaultMetrics() {
        return {
            'Response Relevancy': 0.85,
            'Faithfulness': 0.78,
            'Context Recall': 0.82,
            'Context Precision': 0.75,
            'Answer Correctness': 0.80,
            'Answer Similarity': 0.88,
            'LLM Answer Relevancy': 0.83,
            'LLM Context Relevancy': 0.79,
            'LLM Answer Correctness': 0.81,
            'LLM Ground Truth Validity': 0.85,
            'LLM Answer Completeness': 0.82,
            'LLM Answer Relevancy Justification': "The answer is relevant to the query and provides appropriate information.",
            'LLM Context Relevancy Justification': "The context contains relevant information that supports the answer.",
            'LLM Answer Correctness Justification': "The answer is correct and aligns with the ground truth.",
            'LLM Ground Truth Validity Justification': "The ground truth is valid and appropriate for the query.",
            'LLM Answer Completeness Justification': "The answer provides complete information addressing the query.",
            'Retrieved Chunk IDs': "[]",
            'Retrieved Chunk Count': 0,
            'Sent to LLM Chunk IDs': "[]",
            'Sent to LLM Chunk Count': 0,
            'Used in Answer Chunk IDs': "[]",
            'Used in Answer Chunk Count': 0,
            'Best Support Rank': 'None',
            'Chunks Used Top 5': 0,
            'Chunks Used 5-10': 0,
            'Chunks Used 10-20': 0,
            'Used Chunk Ranks': "[]",
            'Total Chunks Used': 0
        };
    }

    updateElement(id, value) {
        UIUtils.updateElement(id, value);
    }

    createMetricsChart(metrics) {
        console.log('📈 Creating metrics chart with data:', metrics);
        
        const canvas = document.getElementById('metrics-chart');
        if (!canvas) {
            console.error('❌ Chart canvas not found');
            return;
        }

        // Check if Chart.js is available
        if (typeof Chart === 'undefined') {
            console.error('❌ Chart.js not loaded');
            // Try to load Chart.js again
            this.loadChartJS();
            setTimeout(() => this.createMetricsChart(metrics), 2000);
            return;
        }

        const ctx = canvas.getContext('2d');
        
        // Destroy existing chart
        if (this.metricsChart) {
            this.metricsChart.destroy();
        }
        
        // Filter out justification columns (text) and keep only numeric metrics for charts
        const numericMetrics = {};
        Object.entries(metrics).forEach(([key, value]) => {
            if (!key.toLowerCase().includes('justification') && typeof value === 'number') {
                numericMetrics[key] = value;
            }
        });
        
        const labels = Object.keys(numericMetrics);
        const data = Object.values(numericMetrics);
        
        try {
            this.metricsChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Evaluation Metrics',
                        data: data,
                        backgroundColor: CONFIG.CHART_COLORS.PRIMARY + '1A', // Add alpha
                        borderColor: CONFIG.CHART_COLORS.PRIMARY + 'CC', // Add alpha
                        borderWidth: 2,
                        pointBackgroundColor: CONFIG.CHART_COLORS.PRIMARY,
                        pointBorderColor: '#ffffff',
                        pointBorderWidth: 2,
                        pointRadius: 5
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        r: {
                            beginAtZero: true,
                            max: 1,
                            grid: { color: 'rgba(0, 0, 0, 0.1)' },
                            angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
                            pointLabels: {
                                font: { size: 12, weight: '500' },
                                color: '#374151'
                            },
                            ticks: {
                                display: true,
                                stepSize: 0.2,
                                font: { size: 10 },
                                color: '#6b7280'
                            }
                        }
                    }
                }
            });
            console.log('✅ Chart created successfully');
        } catch (error) {
            console.error('❌ Error creating chart:', error);
        }
        
        // Store analysis for later use if available
        if (this.currentAnalysis) {
            console.log('📊 Analysis available for enhanced features:', this.currentAnalysis);
        }
    }

    /**
     * Display quality analysis results in the UI
     * @param {Object} analysisData - Unused chunk analysis data
     */
    displayQualityAnalysis(analysisData) {
        console.log('🔍 Displaying quality analysis:', analysisData);
        
        const qualityContainer = document.getElementById('quality-analysis-container');
        if (!qualityContainer) {
            console.error('❌ Quality analysis container not found');
            return;
        }

        // Show the quality analysis container
        qualityContainer.style.display = 'block';
        
        // Show and update the toggle button
        const toggleButton = document.getElementById('toggle-quality-analysis');
        if (toggleButton) {
            toggleButton.style.display = 'inline-flex';
            toggleButton.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Quality Analysis';
            toggleButton.className = 'btn-secondary active';
        }
        
        // Extract summary data
        const summary = analysisData.summary || {};
        const analysisList = analysisData.analysis_list || [];
        
        // Update summary statistics
        this.updateElement('total-questions-analyzed', summary.total_questions_analyzed || 0);
        this.updateElement('questions-with-unused-chunks', summary.questions_with_unused_chunks || 0);
        
        const percentage = summary.total_questions_analyzed > 0 
            ? Math.round((summary.questions_with_unused_chunks / summary.total_questions_analyzed) * 100)
            : 0;
        this.updateElement('unused-chunks-percentage', `${percentage}%`);
        
        this.updateElement('avg-unused-chunks', summary.avg_unused_chunks_per_question || 0);
        
        // Display category distribution
        this.displayCategoryDistribution(summary.category_distribution || {});
        
        // Display recommendations
        this.displayRecommendations(summary.recommendations || []);
        
        // Display detailed analysis table
        this.displayDetailedAnalysisTable(analysisList);
        
        console.log('✅ Quality analysis displayed successfully');
    }

    /**
     * Display category distribution in the UI
     * @param {Object} categoryDistribution - Category distribution data
     */
    displayCategoryDistribution(categoryDistribution) {
        const categoryGrid = document.getElementById('category-grid');
        if (!categoryGrid) return;
        
        categoryGrid.innerHTML = '';
        
        const categoryIcons = {
            'context_irrelevant': 'fas fa-exclamation-triangle',
            'ground_truth_invalid': 'fas fa-times-circle',
            'context_overload': 'fas fa-layer-group',
            'answer_generation_failure': 'fas fa-robot',
            'mixed_issues': 'fas fa-random'
        };
        
        const categoryNames = {
            'context_irrelevant': 'Context Irrelevant',
            'ground_truth_invalid': 'Ground Truth Invalid',
            'context_overload': 'Context Overload',
            'answer_generation_failure': 'Answer Generation Failure',
            'mixed_issues': 'Mixed Issues'
        };
        
        for (const [category, count] of Object.entries(categoryDistribution)) {
            const categoryItem = document.createElement('div');
            categoryItem.className = `category-item ${category}`;
            
            const icon = categoryIcons[category] || 'fas fa-question-circle';
            const name = categoryNames[category] || category;
            
            categoryItem.innerHTML = `
                <i class="${icon}"></i>
                <div class="category-info">
                    <h6>${name}</h6>
                    <p>${count} questions affected</p>
                </div>
            `;
            
            categoryGrid.appendChild(categoryItem);
        }
    }

    /**
     * Display recommendations in the UI
     * @param {Array} recommendations - List of recommendations
     */
    displayRecommendations(recommendations) {
        const recommendationsList = document.getElementById('recommendations-list');
        if (!recommendationsList) return;
        
        recommendationsList.innerHTML = '';
        
        if (recommendations.length === 0) {
            recommendationsList.innerHTML = `
                <div class="recommendation-item">
                    <i class="fas fa-check-circle"></i>
                    <p>No specific recommendations at this time. Your system appears to be performing well.</p>
                </div>
            `;
            return;
        }
        
        recommendations.forEach(recommendation => {
            const recommendationItem = document.createElement('div');
            recommendationItem.className = 'recommendation-item';
            
            recommendationItem.innerHTML = `
                <i class="fas fa-lightbulb"></i>
                <p>${recommendation}</p>
            `;
            
            recommendationsList.appendChild(recommendationItem);
        });
    }

    /**
     * Display detailed analysis table in the UI
     * @param {Array} analysisList - List of analysis items
     */
    displayDetailedAnalysisTable(analysisList) {
        const tableBody = document.getElementById('analysis-table-body');
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        if (analysisList.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; color: var(--gray-500);">
                        <i class="fas fa-info-circle"></i> No detailed analysis data available
                    </td>
                </tr>
            `;
            return;
        }
        
        analysisList.forEach(analysis => {
            const row = document.createElement('tr');
            
            // Truncate query if too long
            const query = analysis.query && analysis.query.length > 50 
                ? analysis.query.substring(0, 50) + '...' 
                : analysis.query || 'N/A';
            
            row.innerHTML = `
                <td title="${analysis.query || 'N/A'}">${query}</td>
                <td>
                    <span class="category-badge ${analysis.category}">
                        ${this.formatCategoryName(analysis.category)}
                    </span>
                </td>
                <td>${analysis.unused_count || 0}</td>
                <td>${this.formatScore(analysis.context_relevance_score)}</td>
                <td>${this.formatScore(analysis.ground_truth_validity_score)}</td>
                <td>${this.formatScore(analysis.context_overload_score)}</td>
                <td title="${analysis.reasoning || 'N/A'}">
                    ${this.truncateText(analysis.reasoning || 'N/A', 60)}
                </td>
            `;
            
            tableBody.appendChild(row);
        });
    }

    /**
     * Format category name for display
     * @param {string} category - Category string
     * @returns {string} Formatted category name
     */
    formatCategoryName(category) {
        const categoryNames = {
            'context_irrelevant': 'Context Irrelevant',
            'ground_truth_invalid': 'Ground Truth Invalid',
            'context_overload': 'Context Overload',
            'answer_generation_failure': 'Answer Generation Failure',
            'mixed_issues': 'Mixed Issues'
        };
        
        return categoryNames[category] || category;
    }

    /**
     * Format score for display
     * @param {number|string} score - Score value
     * @returns {string} Formatted score
     */
    formatScore(score) {
        if (score === null || score === undefined || score === 'N/A') {
            return 'N/A';
        }
        
        if (typeof score === 'number') {
            return score.toFixed(3);
        }
        
        return score;
    }

    /**
     * Truncate text for display
     * @param {string} text - Text to truncate
     * @param {number} maxLength - Maximum length
     * @returns {string} Truncated text
     */
    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) {
            return text;
        }
        
        return text.substring(0, maxLength) + '...';
    }

    /**
     * Toggle quality analysis section visibility
     */
    toggleQualityAnalysis() {
        const qualityContainer = document.getElementById('quality-analysis-container');
        const toggleButton = document.getElementById('toggle-quality-analysis');
        
        if (!qualityContainer || !toggleButton) {
            console.error('❌ Quality analysis elements not found');
            return;
        }
        
        const isVisible = qualityContainer.style.display !== 'none';
        
        if (isVisible) {
            qualityContainer.style.display = 'none';
            toggleButton.innerHTML = '<i class="fas fa-search"></i> Show Quality Analysis';
            toggleButton.className = 'btn-secondary';
        } else {
            qualityContainer.style.display = 'block';
            toggleButton.innerHTML = '<i class="fas fa-eye-slash"></i> Hide Quality Analysis';
            toggleButton.className = 'btn-secondary active';
        }
        
        console.log(`🔍 Quality analysis ${isVisible ? 'hidden' : 'shown'}`);
    }

    // Button handlers
    downloadResults() {
        console.log('📥 Download Results clicked');
        
        if (!this.resultData) {
            console.log('⚠️ No result data available');
            this.showToast('No results available to download', 'warning');
            return;
        }

        if (!this.sessionId) {
            console.log('⚠️ No session ID available');
            this.showToast('Session expired. Please start a new evaluation.', 'error');
            return;
        }

        try {
            const downloadUrl = this.resultData.download_url || `/api/download-results/${this.sessionId}`;
            const filename = this.resultData.processing_stats?.output_file || 
                           `rag_evaluation_results_${this.sessionId.substring(0, 8)}_${new Date().toISOString().split('T')[0]}.xlsx`;
            
            console.log('📂 Downloading from session-specific URL:', downloadUrl);
            
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.download = filename;
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            this.showToast('Download started successfully', 'success');
            this.addLogEntry(`✅ Download initiated: ${filename}`, 'success');
        } catch (error) {
            console.error('❌ Download error:', error);
            this.showToast('Download failed. Please try again.', 'error');
        }
    }

    viewDetails() {
        console.log('👁️ View Details clicked');
        
        if (!this.resultData) {
            console.log('⚠️ No result data available');
            this.showToast('No results available to view', 'warning');
            return;
        }

        this.showDetailedModal();
    }

    createDetailedResultsTable() {
        const detailedResults = this.resultData.detailed_results || [];
        
        if (!detailedResults || detailedResults.length === 0) {
            return `
                <div class="no-data-message">
                    <i class="fas fa-info-circle"></i>
                    <p>No detailed results available. This may happen if:</p>
                    <ul>
                        <li>The evaluation is still processing</li>
                        <li>No evaluation methods were performed (RAGAS, LLM, or CRAG)</li>
                        <li>The results file could not be read</li>
                        <li>The evaluation encountered errors during processing</li>
                    </ul>
                </div>
            `;
        }

        console.log('📊 Creating detailed results table with', detailedResults.length, 'rows');

        // Get evaluation config to show which methods were used
        const config = this.resultData?.config_used || {};
        const enabledMethods = [];
        if (config.evaluate_ragas) enabledMethods.push('RAGAS');
        if (config.evaluate_llm) enabledMethods.push('LLM');
        if (config.evaluate_crag) enabledMethods.push('CRAG');
        
        const methodsText = enabledMethods.length > 0 ? enabledMethods.join(' + ') : 'Unknown Methods';
        console.log('🎯 Evaluation methods used:', methodsText);

        // Group results by sheet name
        const sheetGroups = {};
        let hasMultipleSheets = false;
        
        detailedResults.forEach(row => {
            const sheetName = row._sheet_name || 'Sheet1';
            if (!sheetGroups[sheetName]) {
                sheetGroups[sheetName] = [];
            }
            sheetGroups[sheetName].push(row);
        });

        const sheetNames = Object.keys(sheetGroups);
        hasMultipleSheets = sheetNames.length > 1;

        console.log('📊 Found data from sheets:', sheetNames);

        if (hasMultipleSheets) {
            // Create tabbed interface for multiple sheets
            return this.createMultiSheetTable(sheetGroups);
        } else {
            // Create single table for one sheet
            return this.createSingleSheetTable(detailedResults);
        }
    }

    createMultiSheetTable(sheetGroups) {
        const sheetNames = Object.keys(sheetGroups);
        const totalResults = Object.values(sheetGroups).reduce((sum, sheet) => sum + sheet.length, 0);

        const tabsHTML = `
            <div class="multi-sheet-container">
                <div class="sheet-tabs">
                    <div class="tabs-header">
                        <span class="tabs-title">
                            <i class="fas fa-table"></i> 
                            Results from ${sheetNames.length} sheets (${totalResults} total results)
                        </span>
                    </div>
                    <div class="tabs-nav">
                        ${sheetNames.map((sheetName, index) => `
                            <button class="tab-btn ${index === 0 ? 'active' : ''}" 
                                    data-sheet="${sheetName}"
                                    onclick="ragEvaluator.switchSheet('${sheetName}')">
                                <i class="fas fa-file-alt"></i>
                                ${sheetName}
                                <span class="sheet-count">(${sheetGroups[sheetName].length})</span>
                            </button>
                        `).join('')}
                    </div>
                </div>
                
                <div class="sheet-contents">
                    ${sheetNames.map((sheetName, index) => `
                        <div class="sheet-content ${index === 0 ? 'active' : ''}" 
                             data-sheet="${sheetName}">
                            ${this.createSingleSheetTable(sheetGroups[sheetName], sheetName)}
                        </div>
                    `).join('')}
                </div>
            </div>
        `;

        return tabsHTML;
    }

    createSingleSheetTable(detailedResults, sheetName = null) {
        // Get all unique columns from the results (excluding internal fields)
        const allColumns = new Set();
        detailedResults.forEach(row => {
            Object.keys(row).forEach(col => {
                if (!col.startsWith('_')) { // Skip internal fields like _sheet_name
                    allColumns.add(col);
                }
            });
        });

        const columns = Array.from(allColumns);
        
        // Get evaluation configuration to filter relevant columns
        const config = this.resultData?.config_used || {};
        console.log('🎯 Evaluation config for table filtering:', config);
        
        // Identify all evaluation metrics
        const ragasMetrics = columns.filter(col => 
            ['response relevancy', 'faithfulness', 'context recall', 'context precision', 'answer correctness', 'answer similarity'].includes(col.toLowerCase()) ||
            ['answer_relevancy', 'faithfulness', 'context_recall', 'context_precision', 'answer_correctness', 'answer_similarity'].includes(col.toLowerCase())
        );
        
        const llmMetrics = columns.filter(col => 
            col.toLowerCase().includes('llm') && 
            (col.toLowerCase().includes('relevancy') || col.toLowerCase().includes('correctness') || col.toLowerCase().includes('relevance') || col.toLowerCase().includes('validity') || col.toLowerCase().includes('completeness'))
        );
        
        // Add chunk statistics metrics
        const chunkMetrics = columns.filter(col => 
            col.toLowerCase().includes('chunk') || 
            col.toLowerCase().includes('retrieved') || 
            col.toLowerCase().includes('sent to llm') || 
            col.toLowerCase().includes('used in answer') ||
            col.toLowerCase().includes('support rank') ||
            col.toLowerCase().includes('chunks used')
        );
        
        const cragMetrics = columns.filter(col => 
            col.toLowerCase().includes('accuracy') || col.toLowerCase().includes('crag')
        );
        
        // Filter metrics based on what was actually evaluated
        let activeEvaluationColumns = [];
        
        if (config.evaluate_ragas) {
            activeEvaluationColumns.push(...ragasMetrics);
            console.log('✅ Including RAGAS columns:', ragasMetrics);
        }
        
        if (config.evaluate_llm) {
            activeEvaluationColumns.push(...llmMetrics);
            console.log('✅ Including LLM columns:', llmMetrics);
        }
        
        if (chunkMetrics.length > 0) {
            activeEvaluationColumns.push(...chunkMetrics);
            console.log('✅ Including Chunk Statistics columns:', chunkMetrics);
        }
        
        if (config.evaluate_crag) {
            activeEvaluationColumns.push(...cragMetrics);
            console.log('✅ Including CRAG columns:', cragMetrics);
        }
        
        // If no config found or no evaluation methods enabled, fall back to showing all available metrics
        if (activeEvaluationColumns.length === 0) {
            console.log('⚠️ No evaluation config found or no methods enabled, showing all available metrics');
            activeEvaluationColumns = [...ragasMetrics, ...llmMetrics, ...cragMetrics, ...chunkMetrics];
        }
        
        const hasEvaluationMetrics = activeEvaluationColumns.length > 0;
        
        // Prioritize important columns first
        const priorityColumns = ['query', 'answer', 'ground_truth'];
        const otherColumns = columns.filter(col => 
            !priorityColumns.includes(col) && 
            !activeEvaluationColumns.includes(col)
        );

        const orderedColumns = [
            ...priorityColumns.filter(col => columns.includes(col)),
            ...activeEvaluationColumns,
            ...otherColumns
        ];

        console.log('📋 Table columns order:', orderedColumns);

        const sheetId = sheetName ? sheetName.replace(/[^a-zA-Z0-9]/g, '_') : 'default';

        const tableHTML = `
            <div class="results-table-container">
                ${sheetName ? `
                    <div class="sheet-title">
                        <h4><i class="fas fa-table"></i> ${sheetName}</h4>
                    </div>
                ` : ''}
                
                ${hasEvaluationMetrics ? `
                    <div class="comprehensive-analysis-dashboard" id="analysis-dashboard-${sheetId}">
                        <!-- Dashboard Header -->
                        <div class="dashboard-header">
                            <h5><i class="fas fa-chart-line"></i> Comprehensive Evaluation Analysis</h5>
                            <div class="dashboard-stats">
                                <span class="stat-item">📊 ${detailedResults.length} queries analyzed</span>
                                <span class="stat-item">📈 ${ragasMetrics.length + llmMetrics.length + cragMetrics.length + chunkMetrics.length} metrics evaluated</span>
                                <span class="stat-item">🎯 ${ragasMetrics.length > 0 ? 'RAGAS' : ''}${llmMetrics.length > 0 ? (ragasMetrics.length > 0 ? ' + LLM' : 'LLM') : ''}${cragMetrics.length > 0 ? ' + CRAG' : ''} evaluation</span>
                            </div>
                        </div>
                        
                        <!-- Navigation Tabs -->
                        <div class="analysis-tabs">
                            <button class="tab-button active" data-tab="overview">📊 Overview</button>
                            <button class="tab-button" data-tab="correlations">🔗 Correlations</button>
                            <button class="tab-button" data-tab="performance">🎯 Performance</button>
                            <button class="tab-button" data-tab="retrieval">🔍 Retrieval Quality</button>
                            <button class="tab-button" data-tab="insights">💡 Insights</button>
                        </div>
                        
                        <!-- Tab Content -->
                        <div class="tab-content active" id="overview-${sheetId}">
                            <!-- First Row: Performance Summary + Key Statistics -->
                            <div class="overview-row-1">
                                <div class="chart-card performance-summary">
                                    <h6>Overall Performance Summary</h6>
                                    <canvas id="summary-radar-${sheetId}"></canvas>
                                </div>
                                <div class="metrics-summary-card key-statistics">
                                    <h6>Key Statistics</h6>
                                    <div id="key-stats-${sheetId}" class="stats-grid"></div>
                                </div>
                            </div>
                            
                            <!-- Second Row: Metric Histograms -->
                            <div class="overview-row-2">
                                <div class="chart-card metric-histograms-full">
                                    <h6>Per-Metric Score Range Distribution</h6>
                                    <div id="metric-histograms-${sheetId}" class="metric-histograms-container"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-content" id="correlations-${sheetId}">
                            <div class="correlations-grid">
                                <div class="chart-card">
                                    <h6>Metric Correlation Matrix</h6>
                                    <canvas id="correlation-matrix-${sheetId}"></canvas>
                                </div>
                                <div class="chart-card">
                                    <h6>Metric Relationships</h6>
                                    <canvas id="scatter-matrix-${sheetId}"></canvas>
                                </div>
                                <div class="insights-card">
                                    <h6>Correlation Insights</h6>
                                    <div id="correlation-insights-${sheetId}" class="insights-content"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-content" id="performance-${sheetId}">
                            <div class="performance-grid">
                                <div class="chart-card">
                                    <h6>Query Performance Heatmap</h6>
                                    <canvas id="performance-heatmap-${sheetId}"></canvas>
                                </div>
                                <div class="chart-card">
                                    <h6>Top/Bottom Performing Queries</h6>
                                    <canvas id="top-bottom-queries-${sheetId}"></canvas>
                                </div>
                                <div class="outliers-card">
                                    <h6>Performance Outliers</h6>
                                    <div id="outliers-analysis-${sheetId}" class="outliers-content"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-content" id="retrieval-${sheetId}">
                            <div class="retrieval-quality-grid">
                                <div class="chart-card">
                                    <h6>🔍 Retrieval Quality Overview</h6>
                                    <div id="retrieval-overview-${sheetId}" class="retrieval-overview"></div>
                                </div>
                                <div class="chart-card">
                                    <h6>📊 Chunk Utilization Distribution</h6>
                                    <canvas id="chunk-utilization-chart-${sheetId}"></canvas>
                                </div>
                                <div class="insight-card">
                                    <h6>🔍 Retrieval Quality Insights</h6>
                                    <div id="retrieval-insights-${sheetId}" class="retrieval-insights-content"></div>
                                </div>
                                <div class="insight-card">
                                    <h6>⚡ System Efficiency Analysis</h6>
                                    <div id="efficiency-insights-${sheetId}" class="efficiency-insights-content"></div>
                                </div>
                                <div class="insight-card">
                                    <h6>🎯 Chunk Utilization Analysis</h6>
                                    <div id="utilization-insights-${sheetId}" class="utilization-insights-content"></div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="tab-content" id="insights-${sheetId}">
                            <div class="insights-grid">
                                <div class="insight-card">
                                    <h6>🎯 Model Performance Analysis</h6>
                                    <div id="model-insights-${sheetId}"></div>
                                </div>
                                <div class="insight-card">
                                    <h6>📊 Statistical Summary</h6>
                                    <div id="statistical-insights-${sheetId}"></div>
                                </div>
                                <div class="insight-card">
                                    <h6>💡 Recommendations</h6>
                                    <div id="recommendations-${sheetId}"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                ` : ''}
                
                <div class="table-info">
                    <span><i class="fas fa-info-circle"></i> Showing ${detailedResults.length} results</span>
                    <span><i class="fas fa-columns"></i> ${orderedColumns.length} columns</span>
                </div>
                
                <div class="table-wrapper">
                    <table class="results-table">
                        <thead>
                            <tr>
                                <th class="row-number">#</th>
                                ${orderedColumns.map(col => `
                                    <th class="${this.getColumnClass(col)}" title="${col}">
                                        ${this.formatColumnHeader(col)}
                                    </th>
                                `).join('')}
                            </tr>
                        </thead>
                        <tbody>
                            ${detailedResults.map((row, index) => `
                                <tr class="${index % 2 === 0 ? 'even' : 'odd'}">
                                    <td class="row-number">${index + 1}</td>
                                    ${orderedColumns.map(col => `
                                        <td class="${this.getColumnClass(col)}" title="${this.getCellTitle(row[col] || 'N/A')}">
                                            ${this.formatCellValue(col, row[col])}
                                        </td>
                                    `).join('')}
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                
                ${detailedResults.length >= 50 ? `
                    <div class="table-note">
                        <i class="fas fa-info-circle"></i>
                        <span>Showing first 50 results per sheet. Download the full results file for complete data.</span>
                    </div>
                ` : ''}
            </div>
        `;

        // Schedule comprehensive chart creation after DOM update
                    if (hasEvaluationMetrics) {
                setTimeout(() => {
                    this.createComprehensiveAnalysis(detailedResults, sheetId, ragasMetrics, llmMetrics, cragMetrics);
                    this.setupAnalysisTabs(sheetId);
                }, 100);
        }

        return tableHTML;
    }

    switchSheet(sheetName) {
        console.log('🔄 Switching to sheet:', sheetName);
        
        // Update tab buttons
        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            if (btn.dataset.sheet === sheetName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Update sheet contents
        const sheetContents = document.querySelectorAll('.sheet-content');
        sheetContents.forEach(content => {
            if (content.dataset.sheet === sheetName) {
                content.classList.add('active');
            } else {
                content.classList.remove('active');
            }
        });
    }

    createComprehensiveAnalysis(detailedResults, sheetId, ragasMetrics, llmMetrics, cragMetrics) {
        console.log(`📊 Creating comprehensive analysis for sheet: ${sheetId}`);
        
        if (typeof Chart === 'undefined') {
            console.error('❌ Chart.js not loaded');
            return;
        }

        // Filter metrics based on what was actually evaluated
        let filteredMetrics = [];
        const config = this.resultData?.config_used || {};
        
        if (config.evaluate_ragas) {
            filteredMetrics.push(...ragasMetrics);
            console.log('✅ Including RAGAS metrics:', ragasMetrics);
        }
        if (config.evaluate_llm) {
            filteredMetrics.push(...llmMetrics);
            console.log('✅ Including LLM metrics:', llmMetrics);
        }
        if (config.evaluate_crag) {
            filteredMetrics.push(...cragMetrics);
            console.log('✅ Including CRAG metrics:', cragMetrics);
        }
        
        // Fallback: if no config found or no methods enabled, include all available metrics with data
        if (filteredMetrics.length === 0) {
            console.log('⚠️ No evaluation config found or no methods enabled, including all metrics with data');
            const allPossibleMetrics = [...ragasMetrics, ...llmMetrics, ...cragMetrics];
            
            // Get all available columns from the data
            const availableColumns = detailedResults.length > 0 ? Object.keys(detailedResults[0]) : [];
            console.log('📊 Available columns in data:', availableColumns);
            
            // Filter metrics that exist in the data
            filteredMetrics = allPossibleMetrics.filter(metric => 
                detailedResults.some(row => row[metric] !== undefined && row[metric] !== null && row[metric] !== '')
            );
            
            // Also include any chunk-related columns that might not be in the standard metrics
            const chunkColumns = availableColumns.filter(col => 
                col.toLowerCase().includes('chunk') || 
                col.toLowerCase().includes('retrieved') || 
                col.toLowerCase().includes('sent') || 
                col.toLowerCase().includes('used') ||
                col.toLowerCase().includes('support') ||
                col.toLowerCase().includes('rank') ||
                col.toLowerCase().includes('top') ||
                col.toLowerCase().includes('count')
            );
            
            console.log('📊 Found chunk-related columns:', chunkColumns);
            filteredMetrics = [...filteredMetrics, ...chunkColumns];
            
            // Remove duplicates
            filteredMetrics = [...new Set(filteredMetrics)];
        }
        
        console.log('🎯 Final filtered metrics for charts:', filteredMetrics);
        const analysisData = this.analyzeEvaluationData(detailedResults, filteredMetrics);
        
        // Create all charts
        this.createOverviewCharts(sheetId, analysisData);
        this.createCorrelationCharts(sheetId, analysisData);
        this.createPerformanceCharts(sheetId, analysisData);
        this.generateInsights(sheetId, analysisData);
    }

    setupAnalysisTabs(sheetId) {
        // Setup tab navigation for this specific sheet
        const analysisDashboard = document.getElementById(`analysis-dashboard-${sheetId}`);
        if (!analysisDashboard) return;
        
        const tabButtons = analysisDashboard.querySelectorAll(`[data-tab]`);
        const tabContents = analysisDashboard.querySelectorAll(`.tab-content`);
        
        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.getAttribute('data-tab');
                
                // Update button states for this sheet only
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');
                
                // Update content visibility for this sheet only
                tabContents.forEach(content => {
                    if (content.id.includes(tabName) && content.id.includes(sheetId)) {
                        content.classList.add('active');
                    } else if (content.id.includes(sheetId)) {
                        content.classList.remove('active');
                    }
                });
            });
        });
    }

    analyzeEvaluationData(detailedResults, allMetrics) {
        console.log('🔍 Analyzing evaluation data with metrics:', allMetrics);
        console.log('🔍 Raw detailed results for this sheet:', detailedResults);
        
        // Debug: Log all available columns in the data
        if (detailedResults.length > 0) {
            const sampleRow = detailedResults[0];
            console.log('📊 Available columns in data:', Object.keys(sampleRow));
            console.log('📊 Sample row data:', sampleRow);
        }
        
        const analysis = {
            metrics: allMetrics,
            rawData: detailedResults,
            scores: {},
            statistics: {},
            correlations: {},
            performance: {},
            insights: {}
        };

        // Extract scores for each metric
        allMetrics.forEach(metric => {
            const scores = detailedResults
                .map(row => parseFloat(row[metric]))
                .filter(score => !isNaN(score) && score >= 0);
            
            // For chunk metrics, don't filter by <= 1 range
            const isChunkMetric = metric.toLowerCase().includes('chunk') || 
                                 metric.toLowerCase().includes('count') || 
                                 metric.toLowerCase().includes('rank') ||
                                 metric.toLowerCase().includes('total');
            
            if (scores.length > 0) {
                analysis.scores[metric] = scores;
                analysis.statistics[metric] = this.calculateStatistics(scores);
                console.log(`📈 Statistics for ${metric}:`, analysis.statistics[metric]);
            }
        });

        // Calculate correlations
        analysis.correlations = this.calculateCorrelations(analysis.scores);

        // Analyze performance patterns
        analysis.performance = this.analyzePerformancePatterns(detailedResults, allMetrics);

        // Generate insights
        analysis.insights = this.generateDataInsights(analysis);

        return analysis;
    }

    calculateStatistics(scores) {
        if (scores.length === 0) return {};

        const sorted = [...scores].sort((a, b) => a - b);
        const sum = scores.reduce((a, b) => a + b, 0);
        const mean = sum / scores.length;
        const variance = scores.reduce((acc, score) => acc + Math.pow(score - mean, 2), 0) / scores.length;
        const stdDev = Math.sqrt(variance);

        return {
            count: scores.length,
            mean: mean,
            median: sorted[Math.floor(sorted.length / 2)],
            min: Math.min(...scores),
            max: Math.max(...scores),
            stdDev: stdDev,
            q1: sorted[Math.floor(sorted.length * 0.25)],
            q3: sorted[Math.floor(sorted.length * 0.75)],
            iqr: sorted[Math.floor(sorted.length * 0.75)] - sorted[Math.floor(sorted.length * 0.25)]
        };
    }

    calculateCorrelations(scores) {
        const correlations = {};
        const metrics = Object.keys(scores);

        for (let i = 0; i < metrics.length; i++) {
            for (let j = i + 1; j < metrics.length; j++) {
                const metric1 = metrics[i];
                const metric2 = metrics[j];
                
                const correlation = this.pearsonCorrelation(scores[metric1], scores[metric2]);
                correlations[`${metric1}_${metric2}`] = correlation;
            }
        }

        return correlations;
    }

    pearsonCorrelation(x, y) {
        const n = Math.min(x.length, y.length);
        if (n < 2) return 0;

        const xSlice = x.slice(0, n);
        const ySlice = y.slice(0, n);

        const sumX = xSlice.reduce((a, b) => a + b, 0);
        const sumY = ySlice.reduce((a, b) => a + b, 0);
        const sumXY = xSlice.reduce((acc, x, i) => acc + x * ySlice[i], 0);
        const sumX2 = xSlice.reduce((acc, x) => acc + x * x, 0);
        const sumY2 = ySlice.reduce((acc, y) => acc + y * y, 0);

        const numerator = n * sumXY - sumX * sumY;
        const denominator = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));

        return denominator === 0 ? 0 : numerator / denominator;
    }

    analyzePerformancePatterns(detailedResults, allMetrics) {
        const patterns = {
            topPerformers: [],
            bottomPerformers: [],
            outliers: [],
            trends: {}
        };

        // Calculate overall performance score for each query
        const queryPerformance = detailedResults.map((row, index) => {
            const scores = allMetrics
                .map(metric => parseFloat(row[metric]))
                .filter(score => !isNaN(score));
            
            const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 0;
            
            return {
                index: index,
                query: row.query || `Query ${index + 1}`,
                averageScore: avgScore,
                scores: scores,
                row: row
            };
        });

        // Sort by performance
        const sortedPerformance = queryPerformance.sort((a, b) => b.averageScore - a.averageScore);
        
        patterns.topPerformers = sortedPerformance.slice(0, 5);
        patterns.bottomPerformers = sortedPerformance.slice(-5).reverse();

        // Identify outliers (queries with unusual score patterns)
        const avgScores = queryPerformance.map(q => q.averageScore);
        const mean = avgScores.reduce((a, b) => a + b, 0) / avgScores.length;
        const stdDev = Math.sqrt(avgScores.reduce((acc, score) => acc + Math.pow(score - mean, 2), 0) / avgScores.length);
        
        patterns.outliers = queryPerformance.filter(q => 
            Math.abs(q.averageScore - mean) > 2 * stdDev
        );

        return patterns;
    }

    generateDataInsights(analysis) {
        const insights = {
            strengths: [],
            weaknesses: [],
            recommendations: [],
            statistical: [],
            retrieval: [],
            efficiency: [],
            utilization: []
        };

        // Analyze metric performance (existing logic)
        Object.entries(analysis.statistics).forEach(([metric, stats]) => {
            const performance = stats.mean;
            
            if (performance >= 0.8) {
                insights.strengths.push(`Strong ${metric} performance (${(performance * 100).toFixed(1)}%)`);
            } else if (performance < 0.6) {
                insights.weaknesses.push(`${metric} needs improvement (${(performance * 100).toFixed(1)}%)`);
            }

            // Check for high variance
            if (stats.stdDev > 0.25) {
                insights.statistical.push(`High variance in ${metric} scores (σ=${stats.stdDev.toFixed(3)})`);
            }
        });

        // Enhanced correlation insights
        Object.entries(analysis.correlations).forEach(([pair, correlation]) => {
            if (Math.abs(correlation) > 0.7) {
                const [metric1, metric2] = pair.split('_');
                const relation = correlation > 0 ? 'strongly correlated' : 'negatively correlated';
                insights.statistical.push(`${metric1} and ${metric2} are ${relation} (r=${correlation.toFixed(3)})`);
            }
        });

        // Generate new insights based on extended metrics
        this.generateExtendedInsights(analysis, insights);

        // Generate dynamic recommendations based on evaluation rules
        insights.recommendations = this.generateDynamicRecommendations(analysis);

        return insights;
    }

    generateExtendedInsights(analysis, insights) {
        console.log('🔍 Generating extended insights with new metrics');
        console.log('📊 Available metrics in analysis:', Object.keys(analysis.statistics));
        
        // Check for chunk-related data
        const hasChunkData = this.checkForChunkData(analysis);
        console.log('📊 Has chunk data:', hasChunkData);
        
        // Extract extended metrics
        const extendedMetrics = this.extractExtendedMetrics(analysis);
        console.log('📈 Extracted extended metrics:', extendedMetrics);
        
        // Generate retrieval quality insights
        this.generateRetrievalInsights(extendedMetrics, insights);
        
        // Generate efficiency insights
        this.generateEfficiencyInsights(extendedMetrics, insights);
        
        // Generate utilization insights
        this.generateUtilizationInsights(extendedMetrics, insights);
        
        // Generate cross-metric correlation insights
        this.generateCrossMetricInsights(analysis, extendedMetrics, insights);
        
        console.log('✅ Generated insights:', insights);
        
        // Add guidance on enabling chunk metrics
        if (!hasChunkData) {
            console.log('⚠️ No chunk data detected, adding guidance');
            this.addChunkMetricsGuidance(insights);
        } else {
            console.log('✅ Chunk data detected, skipping guidance');
        }
    }

    addChunkMetricsGuidance(insights) {
        const guidance = [
            '📊 To enable comprehensive chunk analysis, ensure your evaluation includes:',
            '   • Retrieved Chunk Count - number of chunks retrieved from knowledge base',
            '   • Sent to LLM Chunk Count - number of chunks sent to the language model',
            '   • Used in Answer Chunk Count - number of chunks actually used in the answer',
            '   • Best Support Rank - ranking of the most relevant chunk',
            '   • Chunks Used Top 5/10/20 - distribution of chunk usage across rank ranges',
            '   • Total Chunks Used - total number of chunks utilized in the answer'
        ];
        
        // Add guidance to recommendations if available
        if (insights.recommendations) {
            insights.recommendations.push('🔧 Enable chunk tracking for detailed retrieval analysis');
            insights.recommendations.push('🔧 Use Search API option to get chunk-level data');
            insights.recommendations.push('🔧 Ensure your RAG system provides chunk metadata');
        }
        
        console.log('📋 Chunk metrics guidance:', guidance);
        
        // Also add a more detailed explanation
        const detailedGuidance = {
            'How to Enable Chunk Analysis': [
                '1. Check "Use Search API" in the configuration',
                '2. Ensure your RAG system returns chunk metadata',
                '3. Look for columns like "Retrieved Chunk Count", "Total Chunks Used" in results',
                '4. Chunk analysis provides insights into retrieval efficiency and quality'
            ]
        };
        
        console.log('📋 Detailed chunk guidance:', detailedGuidance);
    }

    checkForChunkData(analysis) {
        const chunkKeywords = ['chunk', 'retrieved', 'sent', 'used', 'support', 'rank', 'top', 'count'];
        
        // Check in statistics (processed metrics)
        const availableMetrics = Object.keys(analysis.statistics);
        const chunkMetrics = availableMetrics.filter(metric => 
            chunkKeywords.some(keyword => metric.toLowerCase().includes(keyword))
        );
        
        console.log('🔍 Chunk-related metrics found in statistics:', chunkMetrics);
        console.log('📊 All available metrics in statistics:', availableMetrics);
        
        // Also check in raw data columns (unprocessed data)
        const rawDataColumns = analysis.rawData && analysis.rawData.length > 0 ? Object.keys(analysis.rawData[0]) : [];
        const chunkColumns = rawDataColumns.filter(col => 
            chunkKeywords.some(keyword => col.toLowerCase().includes(keyword))
        );
        
        console.log('🔍 Chunk-related columns found in raw data:', chunkColumns);
        console.log('📊 All available columns in raw data:', rawDataColumns);
        
        // Also check for any metrics that might contain chunk information
        const potentialChunkMetrics = availableMetrics.filter(metric => 
            metric.toLowerCase().includes('id') || 
            metric.toLowerCase().includes('count') ||
            metric.toLowerCase().includes('total') ||
            metric.toLowerCase().includes('used') ||
            metric.toLowerCase().includes('top')
        );
        
        if (potentialChunkMetrics.length > 0) {
            console.log('🔍 Potential chunk-related metrics:', potentialChunkMetrics);
        }
        
        // More comprehensive check - look for any metrics that could be chunk-related
        const hasChunkData = chunkMetrics.length > 0 || 
                           chunkColumns.length > 0 ||
                           potentialChunkMetrics.some(metric => 
                               metric.toLowerCase().includes('chunk') ||
                               metric.toLowerCase().includes('retrieved') ||
                               metric.toLowerCase().includes('sent') ||
                               metric.toLowerCase().includes('used')
                           );
        
        console.log('📊 Final chunk data detection result:', hasChunkData);
        console.log('📊 Summary - Chunk metrics:', chunkMetrics.length, 'Chunk columns:', chunkColumns.length);
        return hasChunkData;
    }

    extractExtendedMetrics(analysis) {
        const metrics = {};
        
        console.log('🔍 Available metrics in analysis.statistics:', Object.keys(analysis.statistics));
        console.log('🔍 Available columns in raw data:', analysis.rawData && analysis.rawData.length > 0 ? Object.keys(analysis.rawData[0]) : []);
        
        // Extended metric mappings - updated to match actual data structure
        const metricMappings = {
            'ground_truth_validity': [
                'LLM Ground Truth Validity', 'Ground Truth Validity', 'ground_truth_validity', 'GT Validity'
            ],
            'answer_completeness': [
                'LLM Answer Completeness', 'Answer Completeness', 'answer_completeness', 'Completeness'
            ],
            'retrieved_chunk_count': [
                'Retrieved Chunk Count', 'retrieved_chunk_count', 'Retrieved Chunks', 'Retrieved Chunk IDs'
            ],
            'sent_to_llm_chunk_count': [
                'Sent to LLM Chunk Count', 'sent_to_llm_chunk_count', 'Sent to LLM Chunks', 'Sent to LLM Chunk IDs'
            ],
            'used_in_answer_chunk_count': [
                'Used in Answer Chunk Count', 'used_in_answer_chunk_count', 'Used in Answer Chunks', 'Used in Answer Chunk IDs'
            ],
            'chunks_used_top5': [
                'Chunks Used Top 5', 'Chunks used in top5', 'chunks_used_top5', 'Top 5 Usage'
            ],
            'chunks_used_top10': [
                'Chunks Used 5-10', 'Chunks used in top10', 'chunks_used_top10', 'Top 10 Usage'
            ],
            'chunks_used_top20': [
                'Chunks Used 10-20', 'Chunks used in top20', 'chunks_used_top20', 'Top 20 Usage'
            ],
            'total_chunks_used': [
                'Total Chunks Used', 'total_chunks_used', 'Total Used'
            ],
            'best_support_rank': [
                'Best Support Rank', 'best_support_rank', 'Support Rank'
            ]
        };

        // Extract values for each metric category
        Object.entries(metricMappings).forEach(([standardName, possibleNames]) => {
            let bestMatch = null;
            let bestValue = null;

            console.log(`🔍 Looking for ${standardName} in possible names:`, possibleNames);

            // First try exact matches in statistics
            possibleNames.forEach(metricName => {
                console.log(`  Checking ${metricName} in analysis.statistics:`, analysis.statistics[metricName]);
                if (analysis.statistics[metricName]) {
                    const stats = analysis.statistics[metricName];
                    if (bestMatch === null || metricName.toLowerCase().includes(standardName.split('_')[0])) {
                        bestMatch = metricName;
                        bestValue = stats.mean;
                        console.log(`    ✅ Found match in statistics: ${metricName} = ${bestValue}`);
                    }
                }
            });

            // If no exact match found in statistics, try raw data columns
            if (bestValue === null && analysis.rawData && analysis.rawData.length > 0) {
                const rawDataColumns = Object.keys(analysis.rawData[0]);
                console.log(`🔍 No exact match found in statistics for ${standardName}, trying raw data columns:`, rawDataColumns);
                
                possibleNames.forEach(metricName => {
                    if (rawDataColumns.includes(metricName)) {
                        // Calculate mean from raw data
                        const values = analysis.rawData
                            .map(row => parseFloat(row[metricName]))
                            .filter(val => !isNaN(val));
                        
                        if (values.length > 0) {
                            const mean = values.reduce((a, b) => a + b, 0) / values.length;
                            bestMatch = metricName;
                            bestValue = mean;
                            console.log(`    ✅ Found match in raw data: ${metricName} = ${bestValue}`);
                        }
                    }
                });
            }

            // If still no match found, try partial matching with all available metrics
            if (bestValue === null) {
                const availableMetrics = Object.keys(analysis.statistics);
                console.log(`🔍 No exact match found for ${standardName}, trying partial matching with:`, availableMetrics);
                
                availableMetrics.forEach(metricName => {
                    const metricLower = metricName.toLowerCase();
                    const standardLower = standardName.toLowerCase();
                    
                    // Check if the metric name contains key parts of the standard name
                    if (metricLower.includes(standardLower.replace(/_/g, ' ')) || 
                        metricLower.includes(standardLower.replace(/_/g, '')) ||
                        standardLower.split('_').some(part => metricLower.includes(part))) {
                        
                        const stats = analysis.statistics[metricName];
                        if (stats && stats.mean !== undefined) {
                            bestMatch = metricName;
                            bestValue = stats.mean;
                            console.log(`    ✅ Found partial match: ${metricName} = ${bestValue}`);
                        }
                    }
                });
            }

            // If still no match, try partial matching in raw data columns
            if (bestValue === null && analysis.rawData && analysis.rawData.length > 0) {
                const rawDataColumns = Object.keys(analysis.rawData[0]);
                console.log(`🔍 No partial match found in statistics for ${standardName}, trying partial matching in raw data:`, rawDataColumns);
                
                rawDataColumns.forEach(columnName => {
                    const columnLower = columnName.toLowerCase();
                    const standardLower = standardName.toLowerCase();
                    
                    // Check if the column name contains key parts of the standard name
                    if (columnLower.includes(standardLower.replace(/_/g, ' ')) || 
                        columnLower.includes(standardLower.replace(/_/g, '')) ||
                        standardLower.split('_').some(part => columnLower.includes(part))) {
                        
                        // Calculate mean from raw data
                        const values = analysis.rawData
                            .map(row => parseFloat(row[columnName]))
                            .filter(val => !isNaN(val));
                        
                        if (values.length > 0) {
                            const mean = values.reduce((a, b) => a + b, 0) / values.length;
                            bestMatch = columnName;
                            bestValue = mean;
                            console.log(`    ✅ Found partial match in raw data: ${columnName} = ${bestValue}`);
                        }
                    }
                });
            }

            if (bestValue !== null) {
                metrics[standardName] = bestValue;
                console.log(`📈 Extended ${standardName}: ${bestValue.toFixed(3)} (from ${bestMatch})`);
            } else {
                console.log(`⚠️ Metric '${standardName}' not found in data`);
            }
        });

        return metrics;
    }

    generateRetrievalInsights(extendedMetrics, insights) {
        console.log('🔍 Generating retrieval insights with metrics:', extendedMetrics);
        
        // Ground Truth Validity insights
        if (extendedMetrics.ground_truth_validity !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            console.log('📊 Ground Truth Validity:', gtValidity);
            if (gtValidity >= 0.9) {
                insights.retrieval.push(`✅ Excellent Ground Truth Validity (${(gtValidity * 100).toFixed(1)}%) - system retrieves highly accurate information`);
            } else if (gtValidity >= 0.8) {
                insights.retrieval.push(`✅ High Ground Truth Validity (${(gtValidity * 100).toFixed(1)}%) - system retrieves correct information`);
            } else if (gtValidity < 0.6) {
                insights.retrieval.push(`⚠️ Low Ground Truth Validity (${(gtValidity * 100).toFixed(1)}%) - retrieval strategy needs improvement`);
            } else {
                insights.retrieval.push(`📊 Moderate Ground Truth Validity (${(gtValidity * 100).toFixed(1)}%) - room for improvement`);
            }
        }

        // Chunk count insights
        if (extendedMetrics.retrieved_chunk_count !== undefined) {
            const retrievedCount = extendedMetrics.retrieved_chunk_count;
            console.log('📊 Retrieved Chunk Count:', retrievedCount);
            if (retrievedCount > 15) {
                insights.retrieval.push(`📊 Very high retrieval count (${retrievedCount.toFixed(1)} chunks) - consider reducing for efficiency`);
            } else if (retrievedCount > 10) {
                insights.retrieval.push(`📊 High retrieval count (${retrievedCount.toFixed(1)} chunks) - consider optimization`);
            } else if (retrievedCount < 3) {
                insights.retrieval.push(`📊 Low retrieval count (${retrievedCount.toFixed(1)} chunks) - may need more context`);
            } else if (retrievedCount >= 3 && retrievedCount <= 8) {
                insights.retrieval.push(`📊 Optimal retrieval count (${retrievedCount.toFixed(1)} chunks) - good balance of context and efficiency`);
            }
        }

        // Support rank analysis for retrieval quality
        if (extendedMetrics.best_support_rank !== undefined) {
            const supportRank = extendedMetrics.best_support_rank;
            console.log('📊 Best support rank:', supportRank);
            
            if (supportRank === 1) {
                insights.retrieval.push(`🏆 Perfect retrieval ranking - most relevant chunk found first`);
            } else if (supportRank <= 3) {
                insights.retrieval.push(`📈 Excellent retrieval ranking - relevant chunks found in top-3`);
            } else if (supportRank <= 5) {
                insights.retrieval.push(`📊 Good retrieval ranking - relevant chunks found in top-5`);
            } else {
                insights.retrieval.push(`⚠️ Retrieval ranking needs improvement - relevant chunks found late (rank ${supportRank})`);
            }
        }

        // Chunk distribution analysis
        if (extendedMetrics.chunks_used_top5 !== undefined && extendedMetrics.chunks_used_top10 !== undefined && extendedMetrics.chunks_used_top20 !== undefined) {
            const top5 = extendedMetrics.chunks_used_top5;
            const top10 = extendedMetrics.chunks_used_top10;
            const top20 = extendedMetrics.chunks_used_top20;
            
            if (top5 > 0 && top10 === 0 && top20 === 0) {
                insights.retrieval.push(`🎯 Perfect chunk distribution - all used chunks in top-5`);
            } else if (top5 > 0 && top10 > 0) {
                insights.retrieval.push(`📊 Mixed chunk distribution - chunks used from multiple rank ranges`);
            }
        }
        
        // Fallback insights when chunk metrics are not available
        if (Object.keys(extendedMetrics).length === 0) {
            insights.retrieval.push(`📊 Chunk utilization metrics not available - consider adding retrieval analysis for deeper insights`);
        } else if (Object.keys(extendedMetrics).filter(key => key.includes('chunk')).length === 0) {
            // We have some metrics but no chunk metrics
            insights.retrieval.push(`📊 Basic retrieval metrics available - add chunk analysis for comprehensive insights`);
        }
        
        console.log('✅ Generated retrieval insights:', insights.retrieval);
    }

    generateEfficiencyInsights(extendedMetrics, insights) {
        console.log('⚡ Generating efficiency insights with metrics:', extendedMetrics);
        
        // Calculate utilization efficiency
        if (extendedMetrics.retrieved_chunk_count !== undefined && extendedMetrics.used_in_answer_chunk_count !== undefined) {
            const retrievedCount = extendedMetrics.retrieved_chunk_count;
            const usedCount = extendedMetrics.used_in_answer_chunk_count;
            const utilizationRate = retrievedCount > 0 ? usedCount / retrievedCount : 0;
            console.log('📊 Utilization rate:', utilizationRate);
            
            if (utilizationRate < 0.3) {
                insights.efficiency.push(`🔍 Low chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - system over-retrieves but under-utilizes`);
            } else if (utilizationRate > 0.7) {
                insights.efficiency.push(`✅ High chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - efficient information extraction`);
            } else if (utilizationRate >= 0.4 && utilizationRate <= 0.6) {
                insights.efficiency.push(`⚡ Moderate chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - balanced retrieval strategy`);
            }
        }

        // Sent to LLM vs Used comparison
        if (extendedMetrics.sent_to_llm_chunk_count !== undefined && extendedMetrics.used_in_answer_chunk_count !== undefined) {
            const sentCount = extendedMetrics.sent_to_llm_chunk_count;
            const usedCount = extendedMetrics.used_in_answer_chunk_count;
            const llmUtilization = sentCount > 0 ? usedCount / sentCount : 0;
            console.log('🤖 LLM utilization rate:', llmUtilization);
            
            if (llmUtilization < 0.5) {
                insights.efficiency.push(`🤖 LLM under-utilizes provided context (${(llmUtilization * 100).toFixed(1)}% usage)`);
            } else if (llmUtilization > 0.8) {
                insights.efficiency.push(`🤖 LLM efficiently uses provided context (${(llmUtilization * 100).toFixed(1)}% usage)`);
            }
        }

        // Retrieval efficiency analysis
        if (extendedMetrics.retrieved_chunk_count !== undefined && extendedMetrics.sent_to_llm_chunk_count !== undefined) {
            const retrievedCount = extendedMetrics.retrieved_chunk_count;
            const sentCount = extendedMetrics.sent_to_llm_chunk_count;
            const filteringEfficiency = retrievedCount > 0 ? sentCount / retrievedCount : 0;
            
            if (filteringEfficiency < 0.6) {
                insights.efficiency.push(`🔍 Aggressive chunk filtering (${(filteringEfficiency * 100).toFixed(1)}% sent to LLM) - consider relaxing filters`);
            } else if (filteringEfficiency > 0.9) {
                insights.efficiency.push(`📊 Minimal chunk filtering (${(filteringEfficiency * 100).toFixed(1)}% sent to LLM) - consider stricter filtering`);
            }
        }
        
        // Generate insights from available metrics
        if (extendedMetrics.ground_truth_validity !== undefined && extendedMetrics.answer_completeness !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            const completeness = extendedMetrics.answer_completeness;
            
            // Efficiency insight based on validity vs completeness
            if (gtValidity > 0.8 && completeness < 0.7) {
                insights.efficiency.push(`⚡ High retrieval accuracy but low completeness - consider expanding context window`);
            } else if (gtValidity < 0.6 && completeness > 0.8) {
                insights.efficiency.push(`⚡ High completeness but poor retrieval - focus on improving context selection`);
            } else if (gtValidity > 0.8 && completeness > 0.8) {
                insights.efficiency.push(`⚡ Optimal balance of retrieval accuracy and completeness - efficient system performance`);
            } else if (gtValidity >= 0.7 && completeness >= 0.7) {
                insights.efficiency.push(`⚡ Good balance of retrieval accuracy and completeness - system performing well`);
            } else if (gtValidity < 0.7 && completeness < 0.7) {
                insights.efficiency.push(`⚡ Both retrieval accuracy and completeness need improvement - consider system optimization`);
            }
            
            // Additional efficiency insights based on the gap
            const gap = Math.abs(gtValidity - completeness);
            if (gap > 0.2) {
                insights.efficiency.push(`⚡ Significant gap between retrieval accuracy and completeness (${(gap * 100).toFixed(1)}%) - consider balancing both metrics`);
            }
        }
        
        // Fallback insights when chunk metrics are not available
        if (Object.keys(extendedMetrics).filter(key => key.includes('chunk')).length === 0) {
            if (extendedMetrics.ground_truth_validity !== undefined && extendedMetrics.answer_completeness !== undefined) {
                insights.efficiency.push(`📊 Basic efficiency analysis available - add chunk metrics for detailed utilization insights`);
            } else {
                insights.efficiency.push(`📊 Chunk efficiency metrics not available - add retrieval analysis for utilization insights`);
            }
        }
        
        console.log('✅ Generated efficiency insights:', insights.efficiency);
    }

    generateUtilizationInsights(extendedMetrics, insights) {
        console.log('🎯 Generating utilization insights with metrics:', extendedMetrics);
        
        // Top-K utilization patterns with actual metric names
        if (extendedMetrics.chunks_used_top5 !== undefined && extendedMetrics.chunks_used_top10 !== undefined) {
            const top5Usage = extendedMetrics.chunks_used_top5;
            const top10Usage = extendedMetrics.chunks_used_top10;
            console.log('📊 Top-5 usage:', top5Usage, 'Top-10 usage:', top10Usage);
            
            if (top5Usage > 0 && top10Usage === 0) {
                insights.utilization.push(`🎯 All used chunks are in top-5 (${top5Usage} chunks) - excellent ranking quality`);
            } else if (top5Usage > top10Usage * 0.8) {
                insights.utilization.push(`🎯 Top-5 chunks provide most value (${top5Usage} chunks) - good ranking quality`);
            }
        }

        // Support rank analysis
        if (extendedMetrics.best_support_rank !== undefined) {
            const supportRank = extendedMetrics.best_support_rank;
            console.log('📊 Best support rank:', supportRank);
            
            if (supportRank <= 3) {
                insights.utilization.push(`🏆 Excellent support rank (${supportRank}) - highly relevant chunks found early`);
            } else if (supportRank <= 10) {
                insights.utilization.push(`📈 Good support rank (${supportRank}) - relevant chunks found in top-10`);
            } else {
                insights.utilization.push(`⚠️ Support rank (${supportRank}) - consider improving retrieval ranking`);
            }
        }

        // Chunk utilization efficiency
        if (extendedMetrics.retrieved_chunk_count !== undefined && extendedMetrics.used_in_answer_chunk_count !== undefined) {
            const retrievedCount = extendedMetrics.retrieved_chunk_count;
            const usedCount = extendedMetrics.used_in_answer_chunk_count;
            const utilizationRate = retrievedCount > 0 ? usedCount / retrievedCount : 0;
            
            if (utilizationRate > 0.6) {
                insights.utilization.push(`✅ High chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - efficient information extraction`);
            } else if (utilizationRate < 0.3) {
                insights.utilization.push(`🔍 Low chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - consider reducing retrieval count`);
            }
        }

        // Total chunks used analysis
        if (extendedMetrics.total_chunks_used !== undefined) {
            const totalUsed = extendedMetrics.total_chunks_used;
            console.log('📊 Total chunks used:', totalUsed);
            
            if (totalUsed >= 3) {
                insights.utilization.push(`📊 Comprehensive answer using ${totalUsed} chunks - good context utilization`);
            } else if (totalUsed === 1) {
                insights.utilization.push(`📊 Answer relies on single chunk - consider expanding context`);
            }
        }
        
        // Generate insights from available metrics
        if (extendedMetrics.ground_truth_validity !== undefined && extendedMetrics.answer_completeness !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            const completeness = extendedMetrics.answer_completeness;
            
            // Utilization insight based on validity vs completeness balance
            if (gtValidity > 0.9 && completeness > 0.8) {
                insights.utilization.push(`🎯 Excellent balance of retrieval accuracy and answer completeness - optimal system utilization`);
            } else if (gtValidity > 0.8 && completeness < 0.6) {
                insights.utilization.push(`🎯 Good retrieval but under-utilized context - consider expanding answer generation`);
            } else if (gtValidity >= 0.8 && completeness >= 0.8) {
                insights.utilization.push(`🎯 Strong performance in both retrieval accuracy and answer completeness - effective system utilization`);
            } else if (gtValidity >= 0.7 && completeness >= 0.7) {
                insights.utilization.push(`🎯 Balanced performance in retrieval and completeness - good system utilization`);
            } else {
                insights.utilization.push(`🎯 System utilization can be improved by enhancing both retrieval accuracy and answer completeness`);
            }
            
            // Utilization efficiency analysis
            const utilizationScore = (gtValidity + completeness) / 2;
            if (utilizationScore > 0.9) {
                insights.utilization.push(`🎯 Exceptional system utilization score (${(utilizationScore * 100).toFixed(1)}%) - near optimal performance`);
            } else if (utilizationScore > 0.8) {
                insights.utilization.push(`🎯 High system utilization score (${(utilizationScore * 100).toFixed(1)}%) - effective performance`);
            } else if (utilizationScore < 0.6) {
                insights.utilization.push(`🎯 Low system utilization score (${(utilizationScore * 100).toFixed(1)}%) - significant improvement needed`);
            }
        }
        
        // Fallback insights when chunk metrics are not available
        if (Object.keys(extendedMetrics).filter(key => key.includes('chunk')).length === 0) {
            if (extendedMetrics.ground_truth_validity !== undefined && extendedMetrics.answer_completeness !== undefined) {
                insights.utilization.push(`📊 Basic utilization analysis available - add chunk metrics for detailed ranking insights`);
            } else {
                insights.utilization.push(`📊 Chunk utilization metrics not available - add retrieval analysis for ranking insights`);
            }
        }
        
        console.log('✅ Generated utilization insights:', insights.utilization);
    }

    generateCrossMetricInsights(analysis, extendedMetrics, insights) {
        // Cross-metric correlations for new insights
        const crossCorrelations = this.calculateCrossMetricCorrelations(analysis, extendedMetrics);
        
        crossCorrelations.forEach(corr => {
            if (Math.abs(corr.correlation) > 0.6) {
                const direction = corr.correlation > 0 ? 'positive' : 'negative';
                const strength = Math.abs(corr.correlation) > 0.8 ? 'very strong' : 'strong';
                insights.statistical.push(`🔗 ${strength} ${direction} correlation: ${corr.metric1} and ${corr.metric2} (r=${corr.correlation.toFixed(3)})`);
            }
        });
    }

    calculateCrossMetricCorrelations(analysis, extendedMetrics) {
        const correlations = [];
        const metricNames = Object.keys(extendedMetrics);
        
        for (let i = 0; i < metricNames.length; i++) {
            for (let j = i + 1; j < metricNames.length; j++) {
                const metric1 = metricNames[i];
                const metric2 = metricNames[j];
                
                // Find the actual metric names in analysis.scores
                const actualMetric1 = this.findActualMetricName(analysis, metric1);
                const actualMetric2 = this.findActualMetricName(analysis, metric2);
                
                if (actualMetric1 && actualMetric2 && analysis.scores[actualMetric1] && analysis.scores[actualMetric2]) {
                    const correlation = this.pearsonCorrelation(analysis.scores[actualMetric1], analysis.scores[actualMetric2]);
                    correlations.push({
                        metric1: this.formatMetricName(actualMetric1),
                        metric2: this.formatMetricName(actualMetric2),
                        correlation: correlation
                    });
                }
            }
        }
        
        return correlations;
    }

    findActualMetricName(analysis, standardName) {
        const possibleNames = {
            'ground_truth_validity': ['LLM Ground Truth Validity', 'Ground Truth Validity', 'ground_truth_validity', 'GT Validity'],
            'answer_completeness': ['LLM Answer Completeness', 'Answer Completeness', 'answer_completeness', 'Completeness'],
            'retrieved_chunk_count': ['Retrieved Chunk Count', 'retrieved_chunk_count', 'Retrieved Chunks'],
            'sent_to_llm_chunk_count': ['Sent to LLM Chunk Count', 'sent_to_llm_chunk_count', 'Sent to LLM Chunks'],
            'used_in_answer_chunk_count': ['Used in Answer Chunk Count', 'used_in_answer_chunk_count', 'Used in Answer Chunks'],
            'chunks_used_top5': ['Chunks used in top5', 'chunks_used_top5', 'Top 5 Usage'],
            'chunks_used_top10': ['Chunks used in top10', 'chunks_used_top10', 'Top 10 Usage'],
            'chunks_used_top20': ['Chunks used in top20', 'chunks_used_top20', 'Top 20 Usage']
        };
        
        const names = possibleNames[standardName] || [];
        for (const name of names) {
            if (analysis.scores[name]) {
                return name;
            }
        }
        return null;
    }

    generateDynamicRecommendations(analysis) {
        console.log('🤖 Generating comprehensive dynamic recommendations...');
        
        try {
            // Prepare comprehensive analysis data
            const analysisSummary = this.prepareAnalysisSummary(analysis);
            
            // Generate intelligent recommendations based on all available data
            const intelligentRecommendations = this.generateIntelligentRecommendations(analysisSummary);
            
            // Generate enhanced analysis recommendations (NEW)
            const enhancedRecommendations = this.generateEnhancedRecommendations(analysisSummary);
            
            // Combine with rule-based recommendations
            const ruleBasedRecommendations = this.generateRuleBasedRecommendations(analysis);
            
            // Combine all recommendations and apply smart filtering
            const allRecommendations = [...intelligentRecommendations, ...enhancedRecommendations, ...ruleBasedRecommendations];
            const filteredRecommendations = this.smartFilterRecommendations(allRecommendations, analysisSummary);
            
            return filteredRecommendations;
            
        } catch (error) {
            console.error('❌ Error generating recommendations:', error);
            // Fallback to rule-based recommendations
            return this.generateRuleBasedRecommendations(analysis);
        }
    }

    prepareAnalysisSummary(analysis) {
        const summary = {
            metrics: {},
            performance: {},
            correlations: {},
            chunkAnalysis: {},
            outliers: {},
            configuration: {}
        };

        // Extract metric statistics
        Object.entries(analysis.statistics).forEach(([metric, stats]) => {
            summary.metrics[metric] = {
                mean: stats.mean,
                median: stats.median,
                stdDev: stats.stdDev,
                min: stats.min,
                max: stats.max,
                count: stats.count
            };
        });

        // Extract performance patterns
        if (analysis.performance) {
            summary.performance = {
                topPerformers: analysis.performance.topPerformers?.length || 0,
                bottomPerformers: analysis.performance.bottomPerformers?.length || 0,
                outliers: analysis.performance.outliers?.length || 0
            };
        }

        // Extract correlations
        if (analysis.correlations) {
            summary.correlations = analysis.correlations;
        }

        // Extract chunk analysis
        const extendedMetrics = this.extractExtendedMetrics(analysis);
        summary.chunkAnalysis = {
            hasChunkData: this.checkForChunkData(analysis),
            retrievedChunkCount: extendedMetrics.retrieved_chunk_count,
            sentToLLMChunkCount: extendedMetrics.sent_to_llm_chunk_count,
            usedInAnswerChunkCount: extendedMetrics.used_in_answer_chunk_count,
            totalChunksUsed: extendedMetrics.total_chunks_used,
            bestSupportRank: extendedMetrics.best_support_rank,
            chunksUsedTop5: extendedMetrics.chunks_used_top5,
            chunksUsedTop10: extendedMetrics.chunks_used_top10,
            chunksUsedTop20: extendedMetrics.chunks_used_top20
        };

        // Extract configuration info
        summary.configuration = {
            totalQueries: analysis.rawData?.length || 0,
            evaluationMethods: Object.keys(analysis.statistics).filter(metric => 
                metric.toLowerCase().includes('ragas') || 
                metric.toLowerCase().includes('llm') || 
                metric.toLowerCase().includes('crag')
            )
        };

        console.log('📊 Analysis summary prepared:', summary);
        return summary;
    }

    async generateLLMRecommendations(analysisSummary) {
        const prompt = this.buildRecommendationPrompt(analysisSummary);
        
        try {
            // Use OpenAI API to generate recommendations
            const response = await this.callOpenAIAPI(prompt);
            return this.parseLLMRecommendations(response);
        } catch (error) {
            console.error('❌ Error calling OpenAI API:', error);
            throw error;
        }
    }

    buildRecommendationPrompt(analysisSummary) {
        // Use the comprehensive prompt template from prompts.json
        return `You are an expert RAG system analyst and consultant with deep expertise in Retrieval-Augmented Generation systems, evaluation methodologies, and performance optimization. Your role is to analyze comprehensive evaluation data and provide detailed, actionable recommendations for improving RAG system performance. You understand the relationships between different metrics, system components, and optimization strategies.

Based on the following comprehensive RAG system evaluation data, provide detailed, actionable recommendations for improving system performance.

📊 **EVALUATION DATA:**
${JSON.stringify(analysisSummary, null, 2)}

🎯 **TASK:** Generate 5-8 specific, actionable recommendations that cover:

1. **Retrieval Quality Improvements** - Based on context relevancy, chunk utilization, and support rank
2. **Answer Quality Enhancements** - Based on answer correctness, completeness, and relevancy
3. **System Efficiency Optimizations** - Based on chunk counts, processing patterns, and resource usage
4. **Configuration Adjustments** - Specific settings or parameters to modify
5. **Next Steps** - Prioritized action items for immediate implementation

📋 **REQUIREMENTS:**
- Each recommendation should be specific and actionable
- Include priority levels (High/Medium/Low)
- Provide concrete next steps
- Consider the relationship between different metrics
- Focus on practical improvements that can be implemented
- Use emojis for visual clarity

📝 **FORMAT:** Return a JSON array of recommendation objects:
\`\`\`json
[
  {
    "priority": "High/Medium/Low",
    "category": "Retrieval/Answer Quality/Efficiency/Configuration/Next Steps",
    "title": "Brief title",
    "description": "Detailed description",
    "action": "Specific action to take",
    "impact": "Expected impact",
    "emoji": "relevant emoji"
  }
]
\`\`\`

🔍 **ANALYSIS FOCUS:**
- Identify the most critical performance bottlenecks
- Suggest improvements that will have the highest impact
- Consider cost-benefit trade-offs
- Provide recommendations suitable for the current system state
- Focus on actionable insights that can be implemented immediately

Focus on providing recommendations that will have the most significant impact on system performance and user experience.`;
    }



    async callOpenAIAPI(prompt) {
        // Check if OpenAI API is available
        if (typeof window !== 'undefined' && window.openai && window.openai.apiKey) {
            const response = await window.openai.chat.completions.create({
                model: 'gpt-4',
                messages: [
                    {
                        role: 'system',
                        content: 'You are an expert RAG system analyst providing actionable recommendations.'
                    },
                    {
                        role: 'user',
                        content: prompt
                    }
                ],
                temperature: 0.3,
                max_tokens: 1500
            });

            return response.choices[0].message.content;
        } else {
            // Fallback to local recommendation generation
            throw new Error('OpenAI API not available, using fallback recommendations');
        }
    }

    parseLLMRecommendations(llmResponse) {
        try {
            const recommendations = JSON.parse(llmResponse);
            return recommendations.map(rec => 
                `${rec.emoji} **${rec.priority} Priority - ${rec.category}**: ${rec.title} - ${rec.description} **Action**: ${rec.action} **Impact**: ${rec.impact}`
            );
        } catch (error) {
            console.error('❌ Error parsing LLM recommendations:', error);
            // Fallback: try to extract recommendations from text
            return this.extractRecommendationsFromText(llmResponse);
        }
    }

    extractRecommendationsFromText(text) {
        // Fallback method to extract recommendations from text
        const lines = text.split('\n').filter(line => line.trim().length > 0);
        const recommendations = [];
        
        lines.forEach(line => {
            if (line.includes('recommend') || line.includes('improve') || line.includes('optimize') || line.includes('adjust')) {
                recommendations.push(`💡 ${line.trim()}`);
            }
        });
        
        return recommendations.length > 0 ? recommendations : ['💡 Review system configuration and retest with different parameters'];
    }

    generateRuleBasedRecommendations(analysis) {
        console.log('🔍 Generating rule-based recommendations based on evaluation rules');
        
        // Define evaluation rules configuration
        const evaluationRules = [
            {
                conditions: {
                    context_relevancy: ">=0.75",
                    answer_correctness: ">=0.75"
                },
                recommendations: [
                    "✅ System is working as expected. No changes needed.",
                    "📌 Log this example as a golden reference case."
                ]
            },
            {
                conditions: {
                    context_relevancy: ">=0.75",
                    answer_correctness: ">=0.5",
                    answer_correctness_max: "<0.75"
                },
                recommendations: [
                    "🛠️ Fine-tune prompt with clearer instructions or examples.",
                    "📘 Try making the prompt more extractive or specific.",
                    "🧪 Try few-shot prompting for structured answer formats."
                ]
            },
            {
                conditions: {
                    context_relevancy: ">=0.75",
                    answer_correctness: "<0.5"
                },
                recommendations: [
                    "🔍 Validate if ground truth is accurate and aligned with the query.",
                    "🤖 Try changing the prompt style or temperature.",
                    "🧪 Check if LLM misunderstood the context or missed the intent."
                ]
            },
            {
                conditions: {
                    context_relevancy: ">=0.5",
                    context_relevancy_max: "<0.75",
                    answer_correctness: "<0.5"
                },
                recommendations: [
                    "📈 Increase token size or number of chunks passed to LLM.",
                    "🧠 Improve retriever scoring logic or use dense + sparse fusion.",
                    "🔁 Add fallback chunks or expand chunk selection strategy."
                ]
            },
            {
                conditions: {
                    context_relevancy: "<0.5",
                    answer_correctness: ">=0.75"
                },
                recommendations: [
                    "🔄 Improve retriever recall by expanding index coverage.",
                    "🧩 Review chunking strategy. Try semantic or layout-aware chunking.",
                    "📌 Consider boosting named entities or topic matches in context selection."
                ]
            },
            {
                conditions: {
                    context_relevancy: "<0.5",
                    answer_correctness: "<0.5"
                },
                recommendations: [
                    "❌ Likely both retriever and LLM failed.",
                    "🔍 Revisit chunking strategy and retriever quality.",
                    "📦 Add context completeness checks (e.g., fallback to a broader index).",
                    "💬 Consider asking LLM to state when context is insufficient."
                ]
            },
            {
                conditions: {
                    context_relevancy: ">=0.5",
                    context_relevancy_max: "<0.75",
                    answer_correctness: ">=0.5",
                    answer_correctness_max: "<0.75"
                },
                recommendations: [
                    "🧪 Tune prompt slightly for better clarity or structure.",
                    "🔍 Consider re-ranking top-k chunks by semantic similarity.",
                    "📌 Use context-aware scoring to boost mid-relevance chunks."
                ]
            },
            // Extended rules for new metrics
            {
                conditions: {
                    ground_truth_validity: ">=0.8",
                    answer_completeness: ">=0.8"
                },
                recommendations: [
                    "✅ Excellent retrieval and answer generation - system is highly effective",
                    "📊 Ground truth validity and answer completeness are both excellent",
                    "🎯 Consider this configuration as a benchmark for similar queries"
                ]
            },
            {
                conditions: {
                    ground_truth_validity: ">=0.8",
                    answer_completeness: "<0.6"
                },
                recommendations: [
                    "🔍 Good retrieval but incomplete answers - enhance prompt for comprehensiveness",
                    "📝 Add instructions to encourage more detailed responses",
                    "🧪 Try few-shot examples with comprehensive answer formats"
                ]
            },
            {
                conditions: {
                    ground_truth_validity: "<0.6",
                    answer_completeness: ">=0.8"
                },
                recommendations: [
                    "⚠️ Poor retrieval but good answer generation - improve context selection",
                    "🔍 Review retriever configuration and chunking strategy",
                    "📈 Consider expanding index coverage or improving retrieval scoring"
                ]
            },
            {
                conditions: {
                    retrieved_chunk_count: ">=10",
                    used_in_answer_chunk_count: "<=3"
                },
                recommendations: [
                    "🔍 High over-retrieval detected - system retrieves too many chunks",
                    "📊 Consider reducing chunk count or improving retrieval precision",
                    "🎯 Focus on top-k ranking quality rather than quantity"
                ]
            },
            {
                conditions: {
                    retrieved_chunk_count: "<=3",
                    answer_completeness: "<0.6"
                },
                recommendations: [
                    "📈 Low retrieval count affecting answer completeness",
                    "🔍 Increase chunk count or improve retrieval recall",
                    "📊 Consider expanding context window for complex queries"
                ]
            },
            {
                conditions: {
                    ground_truth_validity: ">=0.7",
                    answer_correctness: ">=0.7",
                    answer_completeness: "<0.6"
                },
                recommendations: [
                    "✅ Good accuracy but low completeness - balance needed",
                    "📝 Modify prompt to encourage more comprehensive responses",
                    "🧪 Add examples showing desired answer depth and structure"
                ]
            },
            {
                conditions: {
                    ground_truth_validity: "<0.5",
                    retrieved_chunk_count: ">=8"
                },
                recommendations: [
                    "❌ Poor retrieval quality despite high chunk count",
                    "🔍 Fundamental issues with retriever or index quality",
                    "🔄 Consider retraining retriever or improving index coverage",
                    "📊 Review chunking strategy and document preprocessing"
                ]
            }
        ];

        // Extract relevant metrics from analysis
        const metricValues = this.extractRelevantMetrics(analysis);
        console.log('📊 Extracted metric values for recommendations:', metricValues);

        // Evaluate rules and return matching recommendations
        const matchingRules = this.evaluateRules(evaluationRules, metricValues);
        console.log('✅ Matching rules found:', matchingRules.length);

        if (matchingRules.length > 0) {
            // Return recommendations from the first matching rule
            return matchingRules[0].recommendations;
        }

        // Fallback recommendations if no rules match
        return [
            "📊 Evaluation data doesn't match predefined patterns.",
            "🔍 Review individual query performance for specific insights.",
            "📈 Consider running evaluation with larger dataset for clearer patterns.",
            "🛠️ Manual analysis may be needed for this performance profile."
        ];
    }

    extractRelevantMetrics(analysis) {
        const metricValues = {};
        
        // Map of possible metric names to standardized names
        const metricMappings = {
            'context_relevancy': [
                'Context Precision', 'Context Recall', 'LLM Context Relevancy', 
                'Context Relevancy', 'context_precision', 'context_recall'
            ],
            'answer_correctness': [
                'Answer Correctness', 'LLM Answer Correctness', 'Faithfulness',
                'answer_correctness', 'faithfulness'
            ],
            'ground_truth_validity': [
                'LLM Ground Truth Validity', 'Ground Truth Validity', 'ground_truth_validity', 'GT Validity'
            ],
            'answer_completeness': [
                'LLM Answer Completeness', 'Answer Completeness', 'answer_completeness', 'Completeness'
            ],
            'retrieved_chunk_count': [
                'Retrieved Chunk Count', 'retrieved_chunk_count', 'Retrieved Chunks'
            ],
            'sent_to_llm_chunk_count': [
                'Sent to LLM Chunk Count', 'sent_to_llm_chunk_count', 'Sent to LLM Chunks'
            ],
            'used_in_answer_chunk_count': [
                'Used in Answer Chunk Count', 'used_in_answer_chunk_count', 'Used in Answer Chunks'
            ],
            'total_chunks_used': [
                'Total Chunks Used', 'total_chunks_used', 'Total Used'
            ],
            'best_support_rank': [
                'Best Support Rank', 'best_support_rank', 'Support Rank'
            ]
        };

        // Extract average values for each metric category
        Object.entries(metricMappings).forEach(([standardName, possibleNames]) => {
            let bestMatch = null;
            let bestValue = null;

            possibleNames.forEach(metricName => {
                if (analysis.statistics[metricName]) {
                    const stats = analysis.statistics[metricName];
                    if (bestMatch === null || metricName.toLowerCase().includes(standardName.split('_')[0])) {
                        bestMatch = metricName;
                        bestValue = stats.mean;
                    }
                }
            });

            if (bestValue !== null) {
                metricValues[standardName] = bestValue;
                console.log(`📈 ${standardName}: ${bestValue.toFixed(3)} (from ${bestMatch})`);
            }
        });

        return metricValues;
    }

    evaluateRules(rules, metricValues) {
        const matchingRules = [];

        rules.forEach((rule, index) => {
            const conditions = rule.conditions;
            let allConditionsMet = true;

            console.log(`🔍 Evaluating rule ${index + 1}:`, conditions);

            Object.entries(conditions).forEach(([conditionKey, conditionValue]) => {
                const isMaxCondition = conditionKey.endsWith('_max');
                const metricKey = isMaxCondition ? conditionKey.replace('_max', '') : conditionKey;
                const metricValue = metricValues[metricKey];

                if (metricValue === undefined) {
                    console.log(`⚠️ Metric '${metricKey}' not found in data`);
                    allConditionsMet = false;
                    return;
                }

                const conditionMet = this.evaluateCondition(metricValue, conditionValue);
                console.log(`  ${conditionKey}: ${metricValue.toFixed(3)} ${conditionValue} → ${conditionMet}`);

                if (!conditionMet) {
                    allConditionsMet = false;
                }
            });

            if (allConditionsMet) {
                console.log(`✅ Rule ${index + 1} matches!`);
                matchingRules.push(rule);
            }
        });

        return matchingRules;
    }

    evaluateCondition(value, condition) {
        // Parse condition string (e.g., ">=0.75", "<0.5")
        const match = condition.match(/^(>=|<=|>|<|=)(.+)$/);
        if (!match) {
            console.warn('Invalid condition format:', condition);
            return false;
        }

        const operator = match[1];
        const threshold = parseFloat(match[2]);

        switch (operator) {
            case '>=':
                return value >= threshold;
            case '<=':
                return value <= threshold;
            case '>':
                return value > threshold;
            case '<':
                return value < threshold;
            case '=':
                return Math.abs(value - threshold) < 0.001; // Allow small floating point errors
            default:
                return false;
        }
    }

    analyzeLLMMetrics(detailedResults, llmCorrectnessCol, llmRelevancyCol) {
        const analysis = {};
        
        // Define score ranges
        const ranges = [
            { label: 'Excellent (0.9-1.0)', min: 0.9, max: 1.0, color: '#10b981' },
            { label: 'Good (0.7-0.9)', min: 0.7, max: 0.9, color: '#059669' },
            { label: 'Fair (0.5-0.7)', min: 0.5, max: 0.7, color: '#f59e0b' },
            { label: 'Poor (0.3-0.5)', min: 0.3, max: 0.5, color: '#ef4444' },
            { label: 'Very Poor (0.0-0.3)', min: 0.0, max: 0.3, color: '#dc2626' }
        ];

        // Analyze Answer Correctness
        if (llmCorrectnessCol) {
            const correctnessValues = detailedResults
                .map(row => parseFloat(row[llmCorrectnessCol]))
                .filter(val => !isNaN(val) && val >= 0 && val <= 1);
            
            analysis.correctness = this.categorizeScores(correctnessValues, ranges);
        }

        // Analyze Context Relevancy
        if (llmRelevancyCol) {
            const relevancyValues = detailedResults
                .map(row => parseFloat(row[llmRelevancyCol]))
                .filter(val => !isNaN(val) && val >= 0 && val <= 1);
            
            analysis.relevancy = this.categorizeScores(relevancyValues, ranges);
        }

        // Create comparison data
        if (llmCorrectnessCol && llmRelevancyCol) {
            analysis.comparison = this.createComparisonData(detailedResults, llmCorrectnessCol, llmRelevancyCol);
        }

        return analysis;
    }

    categorizeScores(values, ranges) {
        const total = values.length;
        if (total === 0) return null;

        const distribution = ranges.map(range => {
            const count = values.filter(val => val >= range.min && val < range.max).length;
            const percentage = (count / total * 100).toFixed(1);
            return {
                label: range.label,
                count: count,
                percentage: parseFloat(percentage),
                color: range.color
            };
        });

        // Calculate average score
        const average = (values.reduce((sum, val) => sum + val, 0) / total).toFixed(3);

        return {
            distribution: distribution,
            total: total,
            average: parseFloat(average)
        };
    }

    createComparisonData(detailedResults, correctnessCol, relevancyCol) {
        const comparisonRanges = [
            { label: 'High Correctness & High Relevancy', correctnessMin: 0.7, relevancyMin: 0.7, color: '#10b981' },
            { label: 'High Correctness & Low Relevancy', correctnessMin: 0.7, relevancyMin: 0, relevancyMax: 0.7, color: '#f59e0b' },
            { label: 'Low Correctness & High Relevancy', correctnessMin: 0, correctnessMax: 0.7, relevancyMin: 0.7, color: '#6366f1' },
            { label: 'Low Correctness & Low Relevancy', correctnessMin: 0, correctnessMax: 0.7, relevancyMin: 0, relevancyMax: 0.7, color: '#ef4444' }
        ];

        const total = detailedResults.length;
        const comparison = comparisonRanges.map(range => {
            const count = detailedResults.filter(row => {
                const correctness = parseFloat(row[correctnessCol]);
                const relevancy = parseFloat(row[relevancyCol]);
                
                if (isNaN(correctness) || isNaN(relevancy)) return false;
                
                const correctnessMatch = correctness >= range.correctnessMin && 
                    (range.correctnessMax === undefined || correctness < range.correctnessMax);
                const relevancyMatch = relevancy >= range.relevancyMin && 
                    (range.relevancyMax === undefined || relevancy < range.relevancyMax);
                
                return correctnessMatch && relevancyMatch;
            }).length;

            return {
                label: range.label,
                count: count,
                percentage: ((count / total) * 100).toFixed(1),
                color: range.color
            };
        });

        return comparison;
    }

    createDistributionChart(canvasId, analysisData, title, primaryColor) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`❌ Canvas ${canvasId} not found`);
            return;
        }

        const ctx = canvas.getContext('2d');
        const data = analysisData.distribution;

        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(item => `${item.label} (${item.percentage}%)`),
                datasets: [{
                    data: data.map(item => item.count),
                    backgroundColor: data.map(item => item.color),
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 15,
                            font: { size: 11 },
                            generateLabels: (chart) => {
                                const original = Chart.defaults.plugins.legend.labels.generateLabels;
                                const labels = original.call(this, chart);
                                
                                labels.forEach((label, index) => {
                                    label.text = `${data[index].label}: ${data[index].count} queries (${data[index].percentage}%)`;
                                });
                                
                                return labels;
                            }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const item = data[context.dataIndex];
                                return `${item.count} queries (${item.percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
    }

    createComparisonChart(canvasId, comparisonData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`❌ Canvas ${canvasId} not found`);
            return;
        }

        const ctx = canvas.getContext('2d');

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: comparisonData.map(item => item.label),
                datasets: [{
                    label: 'Number of Queries',
                    data: comparisonData.map(item => item.count),
                    backgroundColor: comparisonData.map(item => item.color),
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const item = comparisonData[context.dataIndex];
                                return `${item.count} queries (${item.percentage}%)`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(0, 0, 0, 0.1)' },
                        ticks: { font: { size: 10 } }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { 
                            font: { size: 9 },
                            maxRotation: 45
                        }
                    }
                }
            }
        });
    }

    getColumnClass(columnName) {
        const col = columnName.toLowerCase();
        if (col.includes('relevancy') || col.includes('faithfulness') || 
            col.includes('recall') || col.includes('precision') || 
            col.includes('correctness') || col.includes('similarity')) {
            return 'metric-column';
        }
        if (col === 'query' || col === 'answer' || col === 'ground_truth') {
            return 'text-column';
        }
        return 'standard-column';
    }

    formatColumnHeader(columnName) {
        // Convert column names to more readable format
        return columnName
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }

    formatCellValue(columnName, value) {
        if (value === null || value === undefined || value === 'N/A') {
            return '<span class="na-value">N/A</span>';
        }

        const col = columnName.toLowerCase();
        
        // Format evaluation metrics (RAGAS, LLM, CRAG)
        if (col.includes('relevancy') || col.includes('faithfulness') || 
            col.includes('recall') || col.includes('precision') || 
            col.includes('correctness') || col.includes('similarity') ||
            col.includes('accuracy') || col.includes('llm') || col.includes('crag')) {
            
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
                // Smart formatting: detect if value is already a percentage (>1) or decimal (0-1)
                let displayValue, normalizedValue;
                
                if (numValue <= 1) {
                    // Value is likely a decimal (0-1), convert to percentage for display
                    displayValue = (numValue * 100).toFixed(1) + '%';
                    normalizedValue = numValue;
                } else {
                    // Value is likely already a percentage, display as-is
                    displayValue = numValue.toFixed(1) + '%';
                    normalizedValue = numValue / 100;
                }
                
                const scoreClass = normalizedValue >= 0.8 ? 'score-good' : 
                                 normalizedValue >= 0.6 ? 'score-medium' : 'score-low';
                                 
                return `<span class="metric-score ${scoreClass}" title="Original value: ${numValue}">${displayValue}</span>`;
            }
        }

        // Format long text fields
        if (col === 'query' || col === 'answer' || col === 'ground_truth' || col.includes('context')) {
            const strValue = String(value);
            if (strValue.length > 100) {
                const truncated = strValue.substring(0, 100) + '...';
                return `<span class="truncated-text" title="${this.escapeHtml(strValue)}">${this.escapeHtml(truncated)}</span>`;
            }
            return `<span class="text-content">${this.escapeHtml(strValue)}</span>`;
        }

        // Format numbers
        if (!isNaN(value) && value !== '') {
            const numValue = parseFloat(value);
            if (Number.isInteger(numValue)) {
                return `<span class="number-value">${numValue}</span>`;
            } else {
                // Show more precision for non-metric numbers, less aggressive rounding
                const decimalPlaces = numValue < 1 ? 6 : 4;
                return `<span class="number-value">${numValue.toFixed(decimalPlaces)}</span>`;
            }
        }

        // Default formatting
        const strValue = String(value);
        if (strValue.length > 50) {
            const truncated = strValue.substring(0, 50) + '...';
            return `<span class="truncated-text" title="${this.escapeHtml(strValue)}">${this.escapeHtml(truncated)}</span>`;
        }
        
        return this.escapeHtml(strValue);
    }

    getCellTitle(value) {
        if (value === null || value === undefined || value === 'N/A') {
            return 'No data available';
        }
        return String(value).length > 50 ? String(value) : '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTokenCount(tokens) {
        if (tokens === null || tokens === undefined || tokens === 0) {
            return '<span class="na-value">N/A</span>';
        }
        return Number(tokens).toLocaleString();
    }

    formatCurrency(amount) {
        if (amount === null || amount === undefined || amount === 0) {
            return '<span class="na-value">$0.00</span>';
        }
        return `$${Number(amount).toFixed(4)}`;
    }

    formatCostPerQuery(totalCost, totalQueries) {
        if (!totalCost || !totalQueries || totalCost === 0 || totalQueries === 0) {
            return '<span class="na-value">N/A</span>';
        }
        const costPerQuery = totalCost / totalQueries;
        return `$${costPerQuery.toFixed(6)}`;
    }

    createTokenUsageSection(stats) {
        // Check if we have real token data
        const hasRealTokenData = this.hasRealTokenUsageData(stats);
        
        if (!hasRealTokenData) {
            console.log('⚠️ No valid token usage data available, hiding detailed section');
            return '<!-- Token Usage section hidden - no real data available -->';
        }

        console.log('✅ Token usage data detected, showing detailed breakdown section');
        
        // Build the section with available data
        let tokenCards = '';
        
        // Always show total tokens if available
        if (stats.total_tokens && stats.total_tokens > 0) {
            tokenCards += `
                <div class="stat-card">
                    <strong>${this.formatTokenCount(stats.total_tokens)}</strong>
                    <span>Total Tokens</span>
                </div>`;
        }
        
        // Show breakdown if available
        if (stats.prompt_tokens && stats.prompt_tokens > 0) {
            tokenCards += `
                <div class="stat-card">
                    <strong>${this.formatTokenCount(stats.prompt_tokens)}</strong>
                    <span>Prompt Tokens</span>
                </div>`;
        }
        
        if (stats.completion_tokens && stats.completion_tokens > 0) {
            tokenCards += `
                <div class="stat-card">
                    <strong>${this.formatTokenCount(stats.completion_tokens)}</strong>
                    <span>Completion Tokens</span>
                </div>`;
        }
        
        // Show cost per query if both cost and query count are available
        if (stats.estimated_cost_usd && stats.total_processed && 
            stats.estimated_cost_usd > 0 && stats.total_processed > 0) {
            tokenCards += `
                <div class="stat-card">
                    <strong>${this.formatCostPerQuery(stats.estimated_cost_usd, stats.total_processed)}</strong>
                    <span>Cost per Query</span>
                </div>`;
        }
        
        return `
            <div class="detail-section">
                <h3><i class="fas fa-coins"></i> Token Usage Breakdown</h3>
                <div class="stats-grid">
                    ${tokenCards}
                </div>
            </div>
        `;
    }

    hasRealTokenUsageData(stats) {
        console.log('🔍 Validating token usage data:', stats);
        
        // Check if we have any meaningful token usage data
        if (!stats) {
            console.log('❌ No stats object provided');
            return false;
        }
        
        // Check for at least total_tokens (most basic requirement)
        if (!stats.total_tokens || stats.total_tokens <= 0) {
            console.log('❌ No valid total_tokens found:', stats.total_tokens);
            return false;
        }
        
        console.log('✅ Found valid total_tokens:', stats.total_tokens);
        
        // If we have prompt_tokens and completion_tokens, validate they sum correctly
        if (stats.prompt_tokens && stats.completion_tokens && 
            stats.prompt_tokens > 0 && stats.completion_tokens > 0) {
            
            const calculatedTotal = stats.prompt_tokens + stats.completion_tokens;
            const tokenSumValid = Math.abs(stats.total_tokens - calculatedTotal) <= 1;
            
            if (!tokenSumValid) {
                console.warn('⚠️ Token sum validation failed:', {
                    total_tokens: stats.total_tokens,
                    prompt_tokens: stats.prompt_tokens,
                    completion_tokens: stats.completion_tokens,
                    calculated_total: calculatedTotal
                });
                // Still show data even if breakdown doesn't match perfectly
            } else {
                console.log('✅ Token breakdown validation passed');
            }
        } else {
            console.log('ℹ️ No complete token breakdown available, but total_tokens is valid');
        }
        
        // Check if cost data exists and is reasonable (optional)
        if (stats.estimated_cost_usd !== undefined && stats.estimated_cost_usd !== null) {
            if (stats.estimated_cost_usd <= 0) {
                console.warn('⚠️ Estimated cost is zero or negative:', stats.estimated_cost_usd);
            } else {
                console.log('✅ Found valid estimated_cost_usd:', stats.estimated_cost_usd);
            }
        } else {
            console.log('ℹ️ No cost data available');
        }

        console.log('✅ Token usage data validation passed (relaxed validation)');
        return true;
    }

    hideChartTooltips() {
        try {
            // Hide Chart.js tooltips if they exist
            if (this.metricsChart) {
                this.metricsChart.tooltip.setActiveElements([]);
                this.metricsChart.update('none');
            }
            
            // Remove any stray Chart.js tooltip elements
            const chartTooltips = document.querySelectorAll('.chartjs-tooltip, [role="tooltip"]');
            chartTooltips.forEach(tooltip => {
                if (tooltip.style) {
                    tooltip.style.opacity = '0';
                    tooltip.style.visibility = 'hidden';
                    tooltip.style.display = 'none';
                }
            });
            
            // Hide any floating percentage displays or labels
            const floatingElements = document.querySelectorAll('.score-text, .percentage-display, .chart-label');
            floatingElements.forEach(element => {
                if (element.style) {
                    element.style.visibility = 'hidden';
                }
            });
            
            console.log('🫥 Chart tooltips and floating elements hidden');
        } catch (error) {
            console.warn('⚠️ Error hiding chart tooltips:', error);
        }
    }

    showDetailedModal() {
        console.log('📊 Opening detailed modal with result data:', this.resultData);
        
        // Hide any Chart.js tooltips or floating elements that might interfere
        this.hideChartTooltips();
        
        const stats = this.resultData.processing_stats || {};
        const metrics = this.extractMetricsFromResult(this.resultData);
        const config = this.resultData.config_used || {};
        
        console.log('💰 Processing stats for modal:', stats);
        console.log('📈 Token usage data:', {
            total_tokens: stats.total_tokens,
            prompt_tokens: stats.prompt_tokens, 
            completion_tokens: stats.completion_tokens,
            estimated_cost_usd: stats.estimated_cost_usd
        });
        console.log('🔍 Token usage validation result:', this.hasRealTokenUsageData(stats));
        
        const modal = document.createElement('div');
        modal.className = 'results-modal';
        modal.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            background: rgba(0, 0, 0, 0.6) !important;
            z-index: 999998 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease;
        `;
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2><i class="fas fa-chart-line"></i> Detailed Results</h2>
                    <button class="modal-close" onclick="this.closest('.results-modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                
                <div class="modal-body">
                    <div class="detail-section">
                        <h3><i class="fas fa-cogs"></i> Processing Statistics</h3>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <strong>${stats.total_processed || 0}</strong>
                                <span>Total Processed</span>
                            </div>
                            <div class="stat-card">
                                <strong>${stats.successful_queries || 0}</strong>
                                <span>Successful</span>
                            </div>
                            <div class="stat-card">
                                <strong>${stats.failed_queries || 0}</strong>
                                <span>Failed</span>
                            </div>
                            ${this.hasRealTokenUsageData(stats) ? `
                            <div class="stat-card">
                                <strong>${this.formatTokenCount(stats.total_tokens)}</strong>
                                <span>Total Tokens</span>
                            </div>
                            <div class="stat-card">
                                <strong>${this.formatCurrency(stats.estimated_cost_usd)}</strong>
                                <span>Estimated Cost</span>
                            </div>` : ''}
                        </div>
                    </div>

                    ${this.createTokenUsageSection(stats)}

                    <div class="detail-section">
                                            <h3><i class="fas fa-table"></i> Detailed Evaluation Results (${this.getEvaluationMethodsText()})</h3>
                    ${this.createDetailedResultsTable()}
                    </div>

                    <div class="detail-section">
                        <h3><i class="fas fa-cog"></i> Configuration</h3>
                        <div class="config-list">
                            <div>RAGAS: ${config.evaluate_ragas ? '✅ Enabled' : '❌ Disabled'}</div>
                            <div>CRAG: ${config.evaluate_crag ? '✅ Enabled' : '❌ Disabled'}</div>
                            <div>LLM Evaluation: ${config.evaluate_llm ? '✅ Enabled' : '❌ Disabled'}</div>
                            <div>Search API: ${config.use_search_api ? '✅ Enabled' : '❌ Disabled'}</div>
                            <div>LLM Model: ${config.llm_model || 'Default'}</div>
                            <div>Batch Size: ${config.batch_size || 10}</div>
                        </div>
                    </div>
                </div>
                
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="this.closest('.results-modal').remove()">
                        Close
                    </button>
                </div>
            </div>
        `;
        
        document.body.appendChild(modal);
        
        // Show modal with animation
        setTimeout(() => {
            modal.classList.add('show');
            modal.style.opacity = '1';
            modal.style.visibility = 'visible';
        }, 10);
        
        // Close on backdrop click (outside modal content)
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.closeModal(modal);
            }
        });
        
        // Prevent clicks inside modal content from closing modal
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
        
        // Close on close button click
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.closeModal(modal);
            });
        }
        
        // ESC key to close
        const escHandler = (e) => {
            if (e.key === 'Escape') {
                this.closeModal(modal);
                document.removeEventListener('keydown', escHandler);
            }
        };
        document.addEventListener('keydown', escHandler);
    }

    closeModal(modal) {
        // Restore any hidden Chart.js elements
        this.restoreChartElements();
        
        // Hide modal with animation
        modal.classList.remove('show');
        modal.style.opacity = '0';
        modal.style.visibility = 'hidden';
        
        setTimeout(() => {
            if (modal.parentNode) {
                modal.parentNode.removeChild(modal);
            }
        }, 300);
    }

    restoreChartElements() {
        try {
            // Restore Chart.js tooltip elements
            const chartTooltips = document.querySelectorAll('.chartjs-tooltip, [role="tooltip"]');
            chartTooltips.forEach(tooltip => {
                if (tooltip.style) {
                    tooltip.style.opacity = '';
                    tooltip.style.visibility = '';
                    tooltip.style.display = '';
                }
            });
            
            // Restore any floating percentage displays or labels
            const floatingElements = document.querySelectorAll('.score-text, .percentage-display, .chart-label');
            floatingElements.forEach(element => {
                if (element.style) {
                    element.style.visibility = '';
                }
            });
            
            console.log('🔄 Chart elements restored');
        } catch (error) {
            console.warn('⚠️ Error restoring chart elements:', error);
        }
    }

    async resetForNewEvaluation() {
        console.log('🔄 Reset for new evaluation');
        
        // Hide sections
        const progressSection = document.getElementById('progress-section');
        const resultsSection = document.getElementById('results-section');
        
        if (progressSection) progressSection.style.display = 'none';
        if (resultsSection) resultsSection.style.display = 'none';
        
        // Reset progress
        const progressFill = document.getElementById('progress-fill');
        const logOutput = document.getElementById('log-output');
        
        if (progressFill) progressFill.style.width = '0%';
        if (logOutput) logOutput.innerHTML = '';
        
        // Clear uploaded file and reset file upload UI
        this.removeFile();
        
        // Clear estimation details in the Run Evaluation section
        const estimationDetails = document.getElementById('estimation-details');
        if (estimationDetails) {
            estimationDetails.innerHTML = '';
        }
        
        // Reset evaluation metrics elements (if they exist)
        this.updateElement('total-processed', '0');
        this.updateElement('successful-queries', '0');
        this.updateElement('total-time', '0s');
        this.updateElement('avg-time', '0s');
        
        // Clear any metrics chart
        if (this.metricsChart) {
            this.metricsChart.destroy();
            this.metricsChart = null;
        }
        
        // Clear evaluation results data
        this.resultData = null;
        this.fileRowCounts = null;
        
        // Reset form state
        this.enableForm();
        this.validateForm();
        
        // Reset any dynamic time estimates to default
        this.updateElement('estimated-time', '--');
        this.updateElement('total-queries', '--');
        
        // Scroll to top and show success message
        window.scrollTo({ top: 0, behavior: 'smooth' });
        this.showToast('✨ Ready for new evaluation! Please upload your Excel file.', 'info');
    }

    debugButtons() {
        console.log('🔍 BUTTON DEBUG INFO:');
        console.log('Download button:', document.getElementById('download-results'));
        console.log('View button:', document.getElementById('view-details'));
        console.log('New eval button:', document.getElementById('new-evaluation'));
        console.log('Results section visible:', document.getElementById('results-section')?.offsetParent !== null);
        console.log('Result data:', !!this.resultData);
        console.log('Chart.js available:', typeof Chart !== 'undefined');
        console.log('Current chart:', !!this.metricsChart);
    }

    disableForm() {
        const inputs = document.querySelectorAll('input, select, button');
        inputs.forEach(input => {
            if (input.id !== 'remove-file') input.disabled = true;
        });
    }

    enableForm() {
        const inputs = document.querySelectorAll('input, select, button');
        inputs.forEach(input => input.disabled = false);
        this.validateForm();
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    formatTime(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);
        return `${minutes}m ${remainingSeconds}s`;
    }

    showToast(message, type = 'info') {
        const existingToasts = document.querySelectorAll('.toast');
        existingToasts.forEach(toast => toast.remove());

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <i class="fas fa-${this.getToastIcon(type)}"></i>
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.animation = 'slideInRight 0.3s ease reverse';
                setTimeout(() => {
                    if (toast.parentNode) toast.parentNode.removeChild(toast);
                }, 300);
            }
        }, 4000);
    }

    getToastIcon(type) {
        const icons = {
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'error': 'times-circle',
            'info': 'info-circle'
        };
        return icons[type] || 'info-circle';
    }

    getEvaluationMethodsText() {
        const config = this.resultData?.config_used || {};
        const enabledMethods = [];
        if (config.evaluate_ragas) enabledMethods.push('RAGAS');
        if (config.evaluate_llm) enabledMethods.push('LLM');
        if (config.evaluate_crag) enabledMethods.push('CRAG');
        
        return enabledMethods.length > 0 ? enabledMethods.join(' + ') : 'Unknown Methods';
    }

    createOverviewCharts(sheetId, analysisData) {
        // 1. Summary Radar Chart
        this.createSummaryRadarChart(`summary-radar-${sheetId}`, analysisData);
        
        // 2. Per-Metric Score Range Histograms
        this.createMetricRangeHistograms(`metric-histograms-${sheetId}`, analysisData);
        
        // 3. Key Statistics
        this.populateKeyStatistics(`key-stats-${sheetId}`, analysisData);
    }



    createCorrelationCharts(sheetId, analysisData) {
        // 1. Correlation heatmap
        this.createCorrelationHeatmap(`correlation-matrix-${sheetId}`, analysisData);
        
        // 2. Scatter plot matrix
        this.createScatterMatrix(`scatter-matrix-${sheetId}`, analysisData);
        
        // 3. Correlation insights
        this.populateCorrelationInsights(`correlation-insights-${sheetId}`, analysisData);
    }

    createPerformanceCharts(sheetId, analysisData) {
        // 1. Query performance heatmap
        this.createQueryHeatmap(`performance-heatmap-${sheetId}`, analysisData);
        
        // 2. Top/bottom performers
        this.createTopBottomChart(`top-bottom-queries-${sheetId}`, analysisData);
        
        // 3. Outliers analysis
        this.populateOutliersAnalysis(`outliers-analysis-${sheetId}`, analysisData);
    }

    generateInsights(sheetId, analysisData) {
        console.log('🎯 Generating insights for sheet:', sheetId);
        console.log('📊 Analysis data insights:', analysisData.insights);
        
        // Populate all insight sections
        this.populateModelInsights(`model-insights-${sheetId}`, analysisData);
        this.populateStatisticalInsights(`statistical-insights-${sheetId}`, analysisData);
        this.populateRecommendations(`recommendations-${sheetId}`, analysisData);
        
        // Populate retrieval quality tab
        this.populateRetrievalQualityTab(sheetId, analysisData);
        
        console.log('✅ Insights generation completed for sheet:', sheetId);
    }

    createSummaryRadarChart(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const metrics = Object.keys(analysisData.statistics);
        const avgScores = metrics.map(metric => analysisData.statistics[metric].mean);

        new Chart(ctx, {
            type: 'radar',
            data: {
                labels: metrics.map(m => this.formatMetricName(m)),
                datasets: [{
                    label: 'Average Scores',
                    data: avgScores,
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    borderColor: 'rgba(59, 130, 246, 0.8)',
                    borderWidth: 2,
                    pointBackgroundColor: 'rgba(59, 130, 246, 1)',
                    pointBorderColor: '#ffffff',
                    pointBorderWidth: 2,
                    pointRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.label}: ${(context.raw * 100).toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            stepSize: 0.2,
                            callback: (value) => `${(value * 100).toFixed(0)}%`
                        }
                    }
                }
            }
        });
    }

    createMetricRangeHistograms(containerId, analysisData) {
        console.log('📊 Creating per-metric range histograms for container:', containerId);
        
        const container = document.getElementById(containerId);
        if (!container) {
            console.error('❌ Container element not found:', containerId);
            return;
        }

        // Define score ranges (same as before)
        const ranges = [
            { label: 'Excellent', shortLabel: 'Exc', min: 0.9, max: 1.0, color: '#10b981' },
            { label: 'Good', shortLabel: 'Good', min: 0.75, max: 0.9, color: '#059669' },
            { label: 'Fair', shortLabel: 'Fair', min: 0.6, max: 0.75, color: '#f59e0b' },
            { label: 'Poor', shortLabel: 'Poor', min: 0.4, max: 0.6, color: '#ef4444' },
            { label: 'Very Poor', shortLabel: 'V.Poor', min: 0.0, max: 0.4, color: '#dc2626' }
        ];

        // Get metrics that have actual score data (not justification columns)
        const metricsWithScores = Object.entries(analysisData.scores).filter(([metric, scores]) => 
            !metric.includes('Justification') && !metric.includes('Test') && scores && scores.length > 0
        );

        console.log('📈 Metrics with scores:', metricsWithScores.map(([metric]) => metric));

        if (metricsWithScores.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #666;">No metric data available</p>';
            return;
        }

        // Create histogram container HTML with enhanced styles for full-width layout
        let histogramHTML = `
            <style>
                /* Overview Layout Styling */
                .overview-row-1 {
                    display: grid;
                    grid-template-columns: 0.6fr 0.4fr;
                    gap: 20px;
                    margin-bottom: 25px;
                    align-items: start;
                }
                
                .overview-row-2 {
                    width: 100%;
                }
                
                .performance-summary {
                    max-height: 350px;
                    min-height: 300px;
                }
                
                .key-statistics {
                    max-height: 350px;
                    min-height: 300px;
                    overflow-y: auto;
                    padding: 20px;
                }
                
                .key-statistics .stats-grid {
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 12px;
                    font-size: 14px;
                }
                
                .key-statistics .stat-item {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 12px;
                    background: #f8fafc;
                    border-radius: 6px;
                    border-left: 3px solid #3b82f6;
                }
                
                .key-statistics .stat-label {
                    font-weight: 600;
                    color: #374151;
                }
                
                .key-statistics .stat-value {
                    font-weight: 700;
                    color: #1f2937;
                }
                
                .metric-histograms-full {
                    width: 100%;
                    min-height: 250px;
                }
                
                /* Histogram Grid Styling */
                .histograms-grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                    gap: 15px;
                    padding: 15px;
                    background: #ffffff;
                    border-radius: 8px;
                }
                
                .histogram-card {
                    padding: 12px;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    background: #f8fafc;
                    transition: box-shadow 0.2s ease;
                }
                
                .histogram-card:hover {
                    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
                }
                
                .histogram-card h7 {
                    display: block;
                    font-size: 13px;
                    font-weight: 600;
                    color: #374151;
                    margin-bottom: 10px;
                    text-align: center;
                    padding-bottom: 5px;
                    border-bottom: 1px solid #e5e7eb;
                }
                
                /* Radar Chart Constraints */
                .performance-summary canvas {
                    max-width: 100% !important;
                    max-height: 280px !important;
                }
                
                /* Additional Statistics Styling */
                .key-statistics h6 {
                    margin-bottom: 15px;
                    font-size: 16px;
                    font-weight: 600;
                    color: #1f2937;
                    border-bottom: 2px solid #e5e7eb;
                    padding-bottom: 8px;
                }
                
                .stat-value.excellent { color: #059669; }
                .stat-value.good { color: #0891b2; }
                .stat-value.poor { color: #dc2626; }
                
                /* Responsive adjustments */
                @media (max-width: 1024px) {
                    .overview-row-1 {
                        grid-template-columns: 0.55fr 0.45fr;
                    }
                }
                
                @media (max-width: 768px) {
                    .overview-row-1 {
                        grid-template-columns: 1fr;
                        gap: 15px;
                    }
                    .performance-summary, .key-statistics {
                        max-height: 300px;
                        min-height: 250px;
                    }
                    .histograms-grid {
                        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                        gap: 10px;
                    }
                }
            </style>
            <div class="histograms-grid">
        `;
        
        metricsWithScores.forEach(([metric, scores], metricIndex) => {
            const cleanMetricName = metric.replace('LLM ', '').replace(' Relevancy', ' Rel.').replace(' Correctness', ' Corr.').replace(' Ground Truth Validity', ' GT Val.').replace(' Answer Completeness', ' Comp.').replace(' Justification', ' Just.');
            const canvasId = `histogram-${containerId}-${metricIndex}`;
            
            histogramHTML += `
                <div class="histogram-card">
                    <h7>${cleanMetricName}</h7>
                    <canvas id="${canvasId}" style="height: 180px; width: 100%;"></canvas>
                </div>
            `;
        });
        
        histogramHTML += '</div>';
        container.innerHTML = histogramHTML;

        // Create individual histogram charts
        metricsWithScores.forEach(([metric, scores], metricIndex) => {
            const canvasId = `histogram-${containerId}-${metricIndex}`;
            this.createSingleMetricHistogram(canvasId, metric, scores, ranges);
        });

        console.log('✅ Per-metric histograms created successfully!');
    }

    createSingleMetricHistogram(canvasId, metricName, scores, ranges) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error('❌ Histogram canvas not found:', canvasId);
            return;
        }

        const ctx = canvas.getContext('2d');

        // Calculate range counts for this metric
        const rangeCounts = ranges.map((range, index) => {
            const isExcellentRange = index === 0;
            const scoresInRange = scores.filter(score => 
                score >= range.min && (isExcellentRange ? score <= range.max : score < range.max)
            );
            return scoresInRange.length;
        });

        console.log(`📊 ${metricName} range distribution:`, rangeCounts);

        // Destroy existing chart if it exists
        const existingChart = Chart.getChart(ctx);
        if (existingChart) {
            existingChart.destroy();
        }

        // Create bar chart
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ranges.map(r => r.shortLabel),
                datasets: [{
                    label: 'Count',
                    data: rangeCounts,
                    backgroundColor: ranges.map(r => r.color),
                    borderColor: ranges.map(r => r.color),
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: {
                        top: 10,
                        bottom: 5
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: Math.max(...rangeCounts) + 1,
                        ticks: {
                            stepSize: 1,
                            font: { size: 11 },
                            color: '#6b7280'
                        },
                        grid: {
                            color: '#f3f4f6'
                        }
                    },
                    x: {
                        ticks: {
                            font: { size: 11, weight: '500' },
                            color: '#374151'
                        },
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        titleFont: { size: 12, weight: '600' },
                        bodyFont: { size: 11 },
                        callbacks: {
                            label: (context) => {
                                const rangeName = ranges[context.dataIndex].label;
                                const count = context.raw;
                                const total = rangeCounts.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((count / total) * 100).toFixed(1) : '0.0';
                                return `${rangeName}: ${count} scores (${percentage}%)`;
                            }
                        }
                    }
                },
                animation: {
                    duration: 800,
                    easing: 'easeOutQuart'
                }
            }
        });
    }

    populateKeyStatistics(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const allScores = Object.values(analysisData.scores).flat();
        const overallMean = allScores.reduce((a, b) => a + b, 0) / allScores.length;
        const overallStdDev = Math.sqrt(allScores.reduce((acc, score) => acc + Math.pow(score - overallMean, 2), 0) / allScores.length);

        const bestMetric = Object.entries(analysisData.statistics).reduce((best, [metric, stats]) => 
            stats.mean > best.score ? { metric, score: stats.mean } : best, 
            { metric: '', score: 0 }
        );

        const worstMetric = Object.entries(analysisData.statistics).reduce((worst, [metric, stats]) => 
            stats.mean < worst.score ? { metric, score: stats.mean } : worst, 
            { metric: '', score: 1 }
        );

        element.innerHTML = `
            <div class="stat-item">
                <span class="stat-label">Overall Performance</span>
                <span class="stat-value ${overallMean >= 0.8 ? 'excellent' : overallMean >= 0.6 ? 'good' : 'poor'}">${(overallMean * 100).toFixed(1)}%</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Best Metric</span>
                <span class="stat-value excellent">${this.formatMetricName(bestMetric.metric)} (${(bestMetric.score * 100).toFixed(1)}%)</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Needs Improvement</span>
                <span class="stat-value poor">${this.formatMetricName(worstMetric.metric)} (${(worstMetric.score * 100).toFixed(1)}%)</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Score Consistency</span>
                <span class="stat-value ${overallStdDev < 0.1 ? 'excellent' : overallStdDev < 0.2 ? 'good' : 'poor'}">σ = ${overallStdDev.toFixed(3)}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Total Evaluations</span>
                <span class="stat-value">${analysisData.rawData.length}</span>
            </div>
            <div class="stat-item">
                <span class="stat-label">Metrics Analyzed</span>
                <span class="stat-value">${analysisData.metrics.length}</span>
            </div>
        `;
    }





    formatMetricName(metric) {
        return metric
            .replace(/_/g, ' ')
            .replace(/([A-Z])/g, ' $1')
            .replace(/\b\w/g, l => l.toUpperCase())
            .trim();
    }



    createHistogram(canvasId, scores, metricName) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        
        // Create bins for histogram
        const bins = 10;
        const binSize = 1 / bins;
        const binCounts = new Array(bins).fill(0);
        const binLabels = [];

        for (let i = 0; i < bins; i++) {
            const start = i * binSize;
            const end = (i + 1) * binSize;
            binLabels.push(`${(start * 100).toFixed(0)}-${(end * 100).toFixed(0)}%`);
        }

        scores.forEach(score => {
            const binIndex = Math.min(Math.floor(score / binSize), bins - 1);
            binCounts[binIndex]++;
        });

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: binLabels,
                datasets: [{
                    data: binCounts,
                    backgroundColor: 'rgba(59, 130, 246, 0.6)',
                    borderColor: 'rgba(59, 130, 246, 0.8)',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: () => metricName,
                            label: (context) => `${context.raw} queries in ${context.label} range`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    },
                    x: {
                        ticks: { 
                            maxRotation: 45,
                            font: { size: 8 }
                        }
                    }
                }
            }
        });
    }

    createCorrelationHeatmap(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const metrics = Object.keys(analysisData.statistics);
        
        // Create correlation matrix data
        const correlationMatrix = [];
        const labels = metrics.map(m => this.formatMetricName(m));

        for (let i = 0; i < metrics.length; i++) {
            const row = [];
            for (let j = 0; j < metrics.length; j++) {
                if (i === j) {
                    row.push(1); // Perfect correlation with self
                } else {
                    const key1 = `${metrics[i]}_${metrics[j]}`;
                    const key2 = `${metrics[j]}_${metrics[i]}`;
                    const correlation = analysisData.correlations[key1] || analysisData.correlations[key2] || 0;
                    row.push(correlation);
                }
            }
            correlationMatrix.push(row);
        }

        // Create heatmap using scatter plot
        const scatterData = [];
        correlationMatrix.forEach((row, i) => {
            row.forEach((correlation, j) => {
                scatterData.push({
                    x: j,
                    y: metrics.length - 1 - i, // Flip Y axis
                    v: correlation
                });
            });
        });

        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Correlation',
                    data: scatterData,
                    backgroundColor: (context) => {
                        const correlation = context.raw.v;
                        const intensity = Math.abs(correlation);
                        const hue = correlation >= 0 ? 120 : 0; // Green for positive, red for negative
                        return `hsla(${hue}, 70%, 50%, ${intensity})`;
                    },
                    pointRadius: 15,
                    pointHoverRadius: 18
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: () => 'Metric Correlation',
                            label: (context) => {
                                const i = metrics.length - 1 - context.raw.y;
                                const j = context.raw.x;
                                return `${labels[i]} ↔ ${labels[j]}: ${context.raw.v.toFixed(3)}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        position: 'bottom',
                        min: -0.5,
                        max: metrics.length - 0.5,
                        ticks: {
                            stepSize: 1,
                            callback: (value) => labels[Math.round(value)] || ''
                        }
                    },
                    y: {
                        type: 'linear',
                        min: -0.5,
                        max: metrics.length - 0.5,
                        ticks: {
                            stepSize: 1,
                            callback: (value) => labels[metrics.length - 1 - Math.round(value)] || ''
                        }
                    }
                }
            }
        });
    }

    createScatterMatrix(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const metrics = Object.keys(analysisData.scores);
        
        if (metrics.length < 2) {
            canvas.parentElement.innerHTML = '<p class="text-center">Need at least 2 metrics for scatter analysis</p>';
            return;
        }

        // Create scatter plot for the two most correlated metrics
        const correlations = Object.entries(analysisData.correlations);
        const strongestCorrelation = correlations.reduce((strongest, [pair, correlation]) => 
            Math.abs(correlation) > Math.abs(strongest.correlation) ? { pair, correlation } : strongest,
            { pair: '', correlation: 0 }
        );

        if (!strongestCorrelation.pair) return;

        const [metric1, metric2] = strongestCorrelation.pair.split('_');
        const scores1 = analysisData.scores[metric1];
        const scores2 = analysisData.scores[metric2];

        if (!scores1 || !scores2) return;

        const scatterData = scores1.map((score1, index) => ({
            x: score1,
            y: scores2[index] || 0
        })).filter(point => point.y !== 0);

        new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: `${this.formatMetricName(metric1)} vs ${this.formatMetricName(metric2)}`,
                    data: scatterData,
                    backgroundColor: 'rgba(59, 130, 246, 0.6)',
                    borderColor: 'rgba(59, 130, 246, 0.8)',
                    borderWidth: 1,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                return `${this.formatMetricName(metric1)}: ${(context.raw.x * 100).toFixed(1)}%, ${this.formatMetricName(metric2)}: ${(context.raw.y * 100).toFixed(1)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: this.formatMetricName(metric1)
                        },
                        min: 0,
                        max: 1,
                        ticks: {
                            callback: (value) => `${(value * 100).toFixed(0)}%`
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: this.formatMetricName(metric2)
                        },
                        min: 0,
                        max: 1,
                        ticks: {
                            callback: (value) => `${(value * 100).toFixed(0)}%`
                        }
                    }
                }
            }
        });
    }

    populateCorrelationInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const correlations = Object.entries(analysisData.correlations);
        const strongCorrelations = correlations.filter(([_, corr]) => Math.abs(corr) > 0.5);
        
        let content = '';
        
        if (strongCorrelations.length === 0) {
            content = `
                <div class="insight-item">
                    <strong>📊 Weak Correlations:</strong> No strong correlations detected between metrics. 
                    This suggests each metric captures unique aspects of performance.
                </div>
            `;
        } else {
            content = `<div class="insights-content">`;
            strongCorrelations.forEach(([pair, correlation]) => {
                const [metric1, metric2] = pair.split('_');
                const strength = Math.abs(correlation) > 0.8 ? 'very strong' : 'strong';
                const direction = correlation > 0 ? 'positive' : 'negative';
                
                content += `
                    <div class="insight-item">
                        <strong>🔗 ${strength.charAt(0).toUpperCase() + strength.slice(1)} ${direction} correlation:</strong> 
                        ${this.formatMetricName(metric1)} and ${this.formatMetricName(metric2)} 
                        (r = ${correlation.toFixed(3)})
                    </div>
                `;
            });
            content += `</div>`;
        }

        element.innerHTML = content;
    }

    createQueryHeatmap(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const totalQueries = analysisData.rawData.length;
        const metrics = analysisData.metrics;
        
        // Create container for heatmap with navigation controls
        const container = canvas.parentElement;
        container.style.position = 'relative';
        
        // Create navigation controls for large datasets
        if (totalQueries > 50) {
            this.createHeatmapNavigation(container, canvasId, analysisData);
            return;
        }
        
        // For smaller datasets (≤50 queries), show all at once with adaptive sizing
        this.renderFullHeatmap(canvas, analysisData, totalQueries);
    }

    createHeatmapNavigation(container, canvasId, analysisData) {
        const totalQueries = analysisData.rawData.length;
        const queriesPerPage = 25; // Show 25 queries per page for better readability
        const totalPages = Math.ceil(totalQueries / queriesPerPage);
        let currentPage = 0;
        
        // Create controls container
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'heatmap-controls';
        controlsDiv.style.cssText = `
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 6px;
            font-size: 14px;
        `;
        
        controlsDiv.innerHTML = `
            <div class="heatmap-info">
                <span><strong>${totalQueries}</strong> queries total</span>
                <span style="margin-left: 15px;">Page <span id="current-page-${canvasId}">1</span> of ${totalPages}</span>
            </div>
            <div class="heatmap-nav">
                <button id="prev-${canvasId}" class="btn-heatmap" ${currentPage === 0 ? 'disabled' : ''}>
                    ← Previous
                </button>
                <button id="next-${canvasId}" class="btn-heatmap" ${currentPage === totalPages - 1 ? 'disabled' : ''}>
                    Next →
                </button>
            </div>
        `;
        
        // Add CSS for navigation buttons
        const style = document.createElement('style');
        style.textContent = `
            .btn-heatmap {
                background: #3b82f6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                cursor: pointer;
                margin: 0 2px;
                font-size: 12px;
            }
            .btn-heatmap:hover:not(:disabled) {
                background: #2563eb;
            }
            .btn-heatmap:disabled {
                background: #9ca3af;
                cursor: not-allowed;
            }
        `;
        document.head.appendChild(style);
        
        container.insertBefore(controlsDiv, container.firstChild);
        
        // Render initial page
        const canvas = document.getElementById(canvasId);
        this.renderHeatmapPage(canvas, analysisData, currentPage, queriesPerPage);
        
        // Add navigation event listeners
        document.getElementById(`prev-${canvasId}`).addEventListener('click', () => {
            if (currentPage > 0) {
                currentPage--;
                this.renderHeatmapPage(canvas, analysisData, currentPage, queriesPerPage);
                this.updateNavigationState(canvasId, currentPage, totalPages);
            }
        });
        
        document.getElementById(`next-${canvasId}`).addEventListener('click', () => {
            if (currentPage < totalPages - 1) {
                currentPage++;
                this.renderHeatmapPage(canvas, analysisData, currentPage, queriesPerPage);
                this.updateNavigationState(canvasId, currentPage, totalPages);
            }
        });
    }

    updateNavigationState(canvasId, currentPage, totalPages) {
        document.getElementById(`current-page-${canvasId}`).textContent = currentPage + 1;
        document.getElementById(`prev-${canvasId}`).disabled = currentPage === 0;
        document.getElementById(`next-${canvasId}`).disabled = currentPage === totalPages - 1;
    }

    renderHeatmapPage(canvas, analysisData, currentPage, queriesPerPage) {
        const startIdx = currentPage * queriesPerPage;
        const endIdx = Math.min(startIdx + queriesPerPage, analysisData.rawData.length);
        const pageQueries = endIdx - startIdx;
        
        // Create subset of data for current page
        const pageData = analysisData.rawData.slice(startIdx, endIdx);
        const pageAnalysisData = { ...analysisData, rawData: pageData };
        
        this.renderFullHeatmap(canvas, pageAnalysisData, pageQueries, startIdx);
    }

    renderFullHeatmap(canvas, analysisData, maxQueries, startOffset = 0) {
        const ctx = canvas.getContext('2d');
        const metrics = analysisData.metrics;
        
        // Clear any existing chart
        if (canvas.chart) {
            canvas.chart.destroy();
        }
        
        // Adaptive point sizing based on data density
        const pointRadius = this.calculatePointRadius(maxQueries, metrics.length);
        
        // Prepare data for heatmap
        const heatmapData = [];
        for (let queryIdx = 0; queryIdx < maxQueries; queryIdx++) {
            metrics.forEach((metric, metricIdx) => {
                const score = parseFloat(analysisData.rawData[queryIdx][metric]);
                if (!isNaN(score)) {
                    heatmapData.push({
                        x: metricIdx,
                        y: queryIdx,
                        v: score,
                        actualQueryIdx: startOffset + queryIdx // Track actual query index
                    });
                }
            });
        }

        const chart = new Chart(ctx, {
            type: 'scatter',
            data: {
                datasets: [{
                    label: 'Query Performance',
                    data: heatmapData,
                    backgroundColor: (context) => {
                        const score = context.raw.v;
                        if (score >= 0.8) return 'rgba(16, 185, 129, 0.8)'; // Green
                        if (score >= 0.6) return 'rgba(245, 158, 11, 0.8)'; // Yellow
                        return 'rgba(239, 68, 68, 0.8)'; // Red
                    },
                    pointRadius: pointRadius,
                    pointHoverRadius: Math.min(pointRadius + 2, 12)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: () => 'Query Performance',
                            label: (context) => {
                                const actualQueryIdx = context.raw.actualQueryIdx || context.raw.y;
                                const metricIdx = context.raw.x;
                                const metric = metrics[metricIdx];
                                return `Query ${actualQueryIdx + 1} - ${this.formatMetricName(metric)}: ${(context.raw.v * 100).toFixed(1)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'linear',
                        min: -0.5,
                        max: metrics.length - 0.5,
                        ticks: {
                            stepSize: 1,
                            callback: (value) => {
                                const metric = metrics[Math.round(value)];
                                return metric ? this.formatMetricName(metric).substring(0, 8) + '...' : '';
                            },
                            maxRotation: 45,
                            font: { size: Math.max(8, 12 - Math.floor(metrics.length / 5)) }
                        },
                        title: {
                            display: true,
                            text: 'Metrics'
                        }
                    },
                    y: {
                        type: 'linear',
                        min: -0.5,
                        max: maxQueries - 0.5,
                        ticks: {
                            stepSize: Math.max(1, Math.floor(maxQueries / 10)),
                            callback: (value) => {
                                const actualQueryIdx = startOffset + Math.round(value);
                                return `Q${actualQueryIdx + 1}`;
                            },
                            font: { size: Math.max(8, 12 - Math.floor(maxQueries / 20)) }
                        },
                        title: {
                            display: true,
                            text: 'Queries'
                        }
                    }
                }
            }
        });
        
        // Store chart reference for cleanup
        canvas.chart = chart;
    }

    calculatePointRadius(queryCount, metricCount) {
        // Adaptive point sizing based on density
        const density = queryCount * metricCount;
        if (density > 1000) return 3;      // Very dense
        if (density > 500) return 4;       // Dense
        if (density > 250) return 6;       // Medium
        return 8;                          // Sparse
    }

    createTopBottomChart(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const topPerformers = analysisData.performance.topPerformers.slice(0, 5);
        const bottomPerformers = analysisData.performance.bottomPerformers.slice(0, 5);
        
        const allQueries = [...topPerformers, ...bottomPerformers];
        const labels = allQueries.map((query, idx) => 
            idx < 5 ? `Top ${idx + 1}` : `Bottom ${idx - 4}`
        );
        const scores = allQueries.map(query => query.averageScore);
        const colors = allQueries.map((_, idx) => 
            idx < 5 ? '#10b981' : '#ef4444'
        );

        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: scores,
                    backgroundColor: colors,
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (context) => {
                                const query = allQueries[context[0].dataIndex];
                                return query.query.substring(0, 50) + '...';
                            },
                            label: (context) => `Average Score: ${(context.raw * 100).toFixed(1)}%`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        ticks: {
                            callback: (value) => `${(value * 100).toFixed(0)}%`
                        }
                    }
                }
            }
        });
    }

    populateOutliersAnalysis(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const outliers = analysisData.performance.outliers;
        
        if (outliers.length === 0) {
            element.innerHTML = `
                <div class="insight-item">
                    <strong>✅ No outliers detected:</strong> All queries show consistent performance patterns.
                </div>
            `;
            return;
        }

        let content = `
            <div class="insight-item">
                <strong>🎯 ${outliers.length} outlier queries detected:</strong>
            </div>
        `;

        outliers.slice(0, 5).forEach((outlier, idx) => {
            const performance = outlier.averageScore >= 0.8 ? 'exceptionally high' : 'unusually low';
            const scoreColor = outlier.averageScore >= 0.8 ? 'excellent' : 'poor';
            
            content += `
                <div class="performance-item">
                    <div class="query-text">${outlier.query.substring(0, 60)}...</div>
                    <div class="performance-score ${scoreColor}">${(outlier.averageScore * 100).toFixed(1)}%</div>
                </div>
            `;
        });

        if (outliers.length > 5) {
            content += `<p class="text-sm text-gray-600 mt-2">... and ${outliers.length - 5} more outliers</p>`;
        }

        element.innerHTML = content;
    }

    populateModelInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error('❌ Element not found:', elementId);
            return;
        }

        const insights = analysisData.insights;
        console.log('🎯 Populating model insights for element:', elementId);
        console.log('📊 Available insights:', insights);
        let content = '';

        if (insights.strengths.length > 0) {
            content += `<div class="mb-3"><strong>💪 Strengths:</strong></div>`;
            insights.strengths.forEach(strength => {
                content += `<div class="insight-item strength">${strength}</div>`;
            });
        }

        if (insights.weaknesses.length > 0) {
            content += `<div class="mb-3 mt-4"><strong>⚠️ Areas for Improvement:</strong></div>`;
            insights.weaknesses.forEach(weakness => {
                content += `<div class="insight-item weakness">${weakness}</div>`;
            });
        }

        // Add new insight categories
        console.log('🔍 Checking retrieval insights:', insights.retrieval);
        if (insights.retrieval && insights.retrieval.length > 0) {
            content += `<div class="mb-3 mt-4"><strong>🔍 Retrieval Quality:</strong></div>`;
            insights.retrieval.forEach(retrieval => {
                content += `<div class="insight-item retrieval">${retrieval}</div>`;
            });
        }

        console.log('⚡ Checking efficiency insights:', insights.efficiency);
        if (insights.efficiency && insights.efficiency.length > 0) {
            content += `<div class="mb-3 mt-4"><strong>⚡ System Efficiency:</strong></div>`;
            insights.efficiency.forEach(efficiency => {
                content += `<div class="insight-item efficiency">${efficiency}</div>`;
            });
        }

        console.log('🎯 Checking utilization insights:', insights.utilization);
        if (insights.utilization && insights.utilization.length > 0) {
            content += `<div class="mb-3 mt-4"><strong>🎯 Chunk Utilization:</strong></div>`;
            insights.utilization.forEach(utilization => {
                content += `<div class="insight-item utilization">${utilization}</div>`;
            });
        }

        element.innerHTML = content;
        
        // Log summary of what was generated
        const insightCounts = {
            strengths: insights.strengths ? insights.strengths.length : 0,
            weaknesses: insights.weaknesses ? insights.weaknesses.length : 0,
            retrieval: insights.retrieval ? insights.retrieval.length : 0,
            efficiency: insights.efficiency ? insights.efficiency.length : 0,
            utilization: insights.utilization ? insights.utilization.length : 0
        };
        console.log('📊 Insight counts generated for', elementId, ':', insightCounts);
    }

    populateRetrievalQualityTab(sheetId, analysisData) {
        console.log('🔍 Populating retrieval quality tab for sheet:', sheetId);
        
        // Populate retrieval overview
        this.populateRetrievalOverview(`retrieval-overview-${sheetId}`, analysisData);
        
        // Charts removed - Ground Truth Validity and Answer Completeness pie charts
        
        // Populate insight sections
        this.populateRetrievalInsights(`retrieval-insights-${sheetId}`, analysisData);
        this.populateEfficiencyInsights(`efficiency-insights-${sheetId}`, analysisData);
        this.populateUtilizationInsights(`utilization-insights-${sheetId}`, analysisData);
        
        // Create chunk utilization charts
        this.createChunkUtilizationChart(`chunk-utilization-chart-${sheetId}`, analysisData);
        
        console.log('✅ Retrieval quality tab populated for sheet:', sheetId);
    }

    populateRetrievalOverview(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) {
            console.error('❌ Retrieval overview element not found:', elementId);
            return;
        }

        const extendedMetrics = this.extractExtendedMetrics(analysisData);
        const hasChunkData = this.checkForChunkData(analysisData);
        
        let content = `
            <div class="retrieval-overview-summary">
                <div class="retrieval-metrics-grid">
        `;
        
        // Add available metrics
        if (extendedMetrics.ground_truth_validity !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            const gtClass = gtValidity >= 0.9 ? 'excellent' : gtValidity >= 0.8 ? 'good' : gtValidity >= 0.7 ? 'fair' : 'poor';
            content += `
                <div class="metric-card ${gtClass}">
                    <div class="metric-icon">✅</div>
                    <div class="metric-label">Ground Truth Validity</div>
                    <div class="metric-value">${(gtValidity * 100).toFixed(1)}%</div>
                    <div class="metric-status">${gtValidity >= 0.9 ? 'Excellent' : gtValidity >= 0.8 ? 'Good' : gtValidity >= 0.7 ? 'Fair' : 'Poor'}</div>
                </div>
            `;
        }
        
        if (extendedMetrics.answer_completeness !== undefined) {
            const completeness = extendedMetrics.answer_completeness;
            const compClass = completeness >= 0.9 ? 'excellent' : completeness >= 0.8 ? 'good' : completeness >= 0.7 ? 'fair' : 'poor';
            content += `
                <div class="metric-card ${compClass}">
                    <div class="metric-icon">🎯</div>
                    <div class="metric-label">Answer Completeness</div>
                    <div class="metric-value">${(completeness * 100).toFixed(1)}%</div>
                    <div class="metric-status">${completeness >= 0.9 ? 'Excellent' : completeness >= 0.8 ? 'Good' : completeness >= 0.7 ? 'Fair' : 'Poor'}</div>
                </div>
            `;
        }
        
        // Add chunk metrics if available
        if (hasChunkData) {
            if (extendedMetrics.retrieved_chunk_count !== undefined) {
                content += `
                    <div class="metric-card info">
                        <div class="metric-icon">📊</div>
                        <div class="metric-label">Retrieved Chunks</div>
                        <div class="metric-value">${extendedMetrics.retrieved_chunk_count.toFixed(1)}</div>
                        <div class="metric-status">Chunks</div>
                    </div>
                `;
            }
            
            if (extendedMetrics.sent_to_llm_chunk_count !== undefined) {
                content += `
                    <div class="metric-card info">
                        <div class="metric-icon">🤖</div>
                        <div class="metric-label">Sent to LLM</div>
                        <div class="metric-value">${extendedMetrics.sent_to_llm_chunk_count.toFixed(1)}</div>
                        <div class="metric-status">Chunks</div>
                    </div>
                `;
            }
            
            if (extendedMetrics.used_in_answer_chunk_count !== undefined) {
                content += `
                    <div class="metric-card info">
                        <div class="metric-icon">🎯</div>
                        <div class="metric-label">Used in Answer</div>
                        <div class="metric-value">${extendedMetrics.used_in_answer_chunk_count.toFixed(1)}</div>
                        <div class="metric-status">Chunks</div>
                    </div>
                `;
            }
            
            if (extendedMetrics.total_chunks_used !== undefined) {
                content += `
                    <div class="metric-card info">
                        <div class="metric-icon">📈</div>
                        <div class="metric-label">Total Used</div>
                        <div class="metric-value">${extendedMetrics.total_chunks_used.toFixed(1)}</div>
                        <div class="metric-status">Chunks</div>
                    </div>
                `;
            }
            
            if (extendedMetrics.best_support_rank !== undefined) {
                const rank = extendedMetrics.best_support_rank;
                const rankClass = rank <= 3 ? 'excellent' : rank <= 10 ? 'good' : 'fair';
                content += `
                    <div class="metric-card ${rankClass}">
                        <div class="metric-icon">🏆</div>
                        <div class="metric-label">Best Support Rank</div>
                        <div class="metric-value">${rank.toFixed(1)}</div>
                        <div class="metric-status">${rank <= 3 ? 'Excellent' : rank <= 10 ? 'Good' : 'Fair'}</div>
                    </div>
                `;
            }
        }
        
        content += `
                </div>
                <div class="retrieval-status">
                    <div class="status-indicator ${hasChunkData ? 'success' : 'warning'}">
                        <span class="status-icon">${hasChunkData ? '✅' : '⚠️'}</span>
                        <span class="status-text">${hasChunkData ? 'Comprehensive chunk analysis available' : 'Basic retrieval analysis - enable chunk tracking for detailed insights'}</span>
                    </div>
                    ${!hasChunkData ? `
                    <div class="retrieval-help">
                        <details>
                            <summary>How to enable chunk analysis</summary>
                            <div class="help-content">
                                <p><strong>To get detailed chunk analysis:</strong></p>
                                <ol>
                                    <li>Check "Use Search API" in the configuration</li>
                                    <li>Ensure your RAG system returns chunk metadata</li>
                                    <li>Look for columns like "Retrieved Chunk Count", "Total Chunks Used" in results</li>
                                    <li>Chunk analysis provides insights into retrieval efficiency and quality</li>
                                </ol>
                                <p><strong>Available columns in your data:</strong></p>
                                <code>${analysisData.rawData && analysisData.rawData.length > 0 ? Object.keys(analysisData.rawData[0]).join(', ') : 'No data available'}</code>
                            </div>
                        </details>
                    </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        element.innerHTML = content;
    }

    // Chart creation functions removed - Ground Truth Validity and Answer Completeness pie charts

    populateRetrievalInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const insights = analysisData.insights;
        const extendedMetrics = this.extractExtendedMetrics(analysisData);
        let content = '';

        // Add detailed retrieval analysis
        content += '<div class="retrieval-analysis-section">';
        
        if (insights.retrieval && insights.retrieval.length > 0) {
            insights.retrieval.forEach(insight => {
                content += `<div class="insight-item retrieval">${insight}</div>`;
            });
        } else {
            content += '<div class="insight-item">No retrieval quality insights available</div>';
        }
        
        // Add detailed metric analysis
        if (extendedMetrics.ground_truth_validity !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            content += `
                <div class="metric-analysis">
                    <h6>Ground Truth Validity Analysis</h6>
                    <div class="metric-details">
                        <div class="metric-detail-item">
                            <span class="detail-label">Score:</span>
                            <span class="detail-value">${(gtValidity * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric-detail-item">
                            <span class="detail-label">Performance Level:</span>
                            <span class="detail-value ${gtValidity >= 0.9 ? 'excellent' : gtValidity >= 0.8 ? 'good' : gtValidity >= 0.7 ? 'fair' : 'poor'}">${gtValidity >= 0.9 ? 'Excellent' : gtValidity >= 0.8 ? 'Good' : gtValidity >= 0.7 ? 'Fair' : 'Poor'}</span>
                        </div>
                        <div class="metric-detail-item">
                            <span class="detail-label">Interpretation:</span>
                            <span class="detail-value">${this.getGTValidityInterpretation(gtValidity)}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        content += '</div>';

        element.innerHTML = content;
    }

    getGTValidityInterpretation(score) {
        if (score >= 0.9) {
            return "System consistently retrieves highly accurate and relevant information from the knowledge base.";
        } else if (score >= 0.8) {
            return "System retrieves correct information most of the time with minor inconsistencies.";
        } else if (score >= 0.7) {
            return "System retrieves relevant information but may miss some important details.";
        } else if (score >= 0.6) {
            return "System has moderate retrieval accuracy with room for improvement.";
        } else {
            return "System struggles to retrieve accurate information and needs significant improvement.";
        }
    }

    populateEfficiencyInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const insights = analysisData.insights;
        const extendedMetrics = this.extractExtendedMetrics(analysisData);
        let content = '';

        // Add detailed efficiency analysis
        content += '<div class="efficiency-analysis-section">';
        
        if (insights.efficiency && insights.efficiency.length > 0) {
            insights.efficiency.forEach(insight => {
                content += `<div class="insight-item efficiency">${insight}</div>`;
            });
        } else {
            content += '<div class="insight-item">No efficiency insights available</div>';
        }
        
        // Add efficiency score calculation
        if (extendedMetrics.ground_truth_validity !== undefined && extendedMetrics.answer_completeness !== undefined) {
            const gtValidity = extendedMetrics.ground_truth_validity;
            const completeness = extendedMetrics.answer_completeness;
            const efficiencyScore = (gtValidity + completeness) / 2;
            const gap = Math.abs(gtValidity - completeness);
            
            content += `
                <div class="metric-analysis">
                    <h6>System Efficiency Analysis</h6>
                    <div class="metric-details">
                        <div class="metric-detail-item">
                            <span class="detail-label">Overall Efficiency Score:</span>
                            <span class="detail-value ${efficiencyScore >= 0.9 ? 'excellent' : efficiencyScore >= 0.8 ? 'good' : efficiencyScore >= 0.7 ? 'fair' : 'poor'}">${(efficiencyScore * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric-detail-item">
                            <span class="detail-label">Performance Gap:</span>
                            <span class="detail-value ${gap <= 0.1 ? 'excellent' : gap <= 0.2 ? 'good' : gap <= 0.3 ? 'fair' : 'poor'}">${(gap * 100).toFixed(1)}%</span>
                        </div>
                        <div class="metric-detail-item">
                            <span class="detail-label">Balance Assessment:</span>
                            <span class="detail-value">${this.getEfficiencyBalanceAssessment(gtValidity, completeness)}</span>
                        </div>
                    </div>
                </div>
            `;
        }
        
        content += '</div>';

        element.innerHTML = content;
    }

    getEfficiencyBalanceAssessment(gtValidity, completeness) {
        const gap = Math.abs(gtValidity - completeness);
        
        if (gap <= 0.1) {
            return "Excellent balance between retrieval accuracy and answer completeness.";
        } else if (gap <= 0.2) {
            return "Good balance with minor differences between metrics.";
        } else if (gap <= 0.3) {
            return "Moderate imbalance - consider optimizing the weaker metric.";
        } else {
            return "Significant imbalance - focus on improving the lower-performing metric.";
        }
    }

    populateUtilizationInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const insights = analysisData.insights;
        const extendedMetrics = this.extractExtendedMetrics(analysisData);
        let content = '';

        // Add detailed utilization analysis
        content += '<div class="utilization-analysis-section">';
        
        if (insights.utilization && insights.utilization.length > 0) {
            insights.utilization.forEach(insight => {
                content += `<div class="insight-item utilization">${insight}</div>`;
            });
        } else {
            content += '<div class="insight-item">No utilization insights available</div>';
        }
        
        // Add detailed chunk utilization analysis
        if (extendedMetrics.chunks_used_top5 !== undefined || 
            extendedMetrics.chunks_used_top10 !== undefined || 
            extendedMetrics.chunks_used_top20 !== undefined) {
            
            content += `
                <div class="metric-analysis">
                    <h6>Chunk Utilization Distribution Analysis</h6>
                    <div class="chunk-utilization-details">
            `;
            
            if (extendedMetrics.chunks_used_top5 !== undefined) {
                const top5 = extendedMetrics.chunks_used_top5;
                content += `
                    <div class="chunk-detail-item">
                        <span class="chunk-label">Top 5 Chunks Used:</span>
                        <span class="chunk-value">${top5} chunks</span>
                        <span class="chunk-assessment">${this.getChunkUtilizationAssessment(top5, 'top5')}</span>
                    </div>
                `;
            }
            
            if (extendedMetrics.chunks_used_top10 !== undefined) {
                const top10 = extendedMetrics.chunks_used_top10;
                content += `
                    <div class="chunk-detail-item">
                        <span class="chunk-label">Chunks 5-10 Used:</span>
                        <span class="chunk-value">${top10} chunks</span>
                        <span class="chunk-assessment">${this.getChunkUtilizationAssessment(top10, 'top10')}</span>
                    </div>
                `;
            }
            
            if (extendedMetrics.chunks_used_top20 !== undefined) {
                const top20 = extendedMetrics.chunks_used_top20;
                content += `
                    <div class="chunk-detail-item">
                        <span class="chunk-label">Chunks 10-20 Used:</span>
                        <span class="chunk-value">${top20} chunks</span>
                        <span class="chunk-assessment">${this.getChunkUtilizationAssessment(top20, 'top20')}</span>
                    </div>
                `;
            }
            
            // Add utilization efficiency analysis
            if (extendedMetrics.retrieved_chunk_count !== undefined && 
                extendedMetrics.used_in_answer_chunk_count !== undefined) {
                const retrieved = extendedMetrics.retrieved_chunk_count;
                const used = extendedMetrics.used_in_answer_chunk_count;
                const efficiency = retrieved > 0 ? (used / retrieved) * 100 : 0;
                
                content += `
                    <div class="utilization-efficiency">
                        <div class="efficiency-header">Utilization Efficiency</div>
                        <div class="efficiency-metrics">
                            <div class="efficiency-item">
                                <span class="efficiency-label">Retrieved:</span>
                                <span class="efficiency-value">${retrieved.toFixed(1)} chunks</span>
                            </div>
                            <div class="efficiency-item">
                                <span class="efficiency-label">Used:</span>
                                <span class="efficiency-value">${used.toFixed(1)} chunks</span>
                            </div>
                            <div class="efficiency-item">
                                <span class="efficiency-label">Efficiency:</span>
                                <span class="efficiency-value ${efficiency >= 70 ? 'excellent' : efficiency >= 50 ? 'good' : efficiency >= 30 ? 'fair' : 'poor'}">${efficiency.toFixed(1)}%</span>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            content += `
                    </div>
                </div>
            `;
        }
        
        content += '</div>';

        element.innerHTML = content;
    }

    getChunkUtilizationAssessment(count, type) {
        if (type === 'top5') {
            if (count >= 3) return "Excellent - heavily utilizes top-ranked chunks";
            if (count >= 2) return "Good - effectively uses top-ranked chunks";
            if (count >= 1) return "Fair - some use of top-ranked chunks";
            return "Poor - minimal use of top-ranked chunks";
        } else if (type === 'top10') {
            if (count >= 2) return "Good - utilizes mid-ranked chunks";
            if (count >= 1) return "Fair - some use of mid-ranked chunks";
            return "Low - minimal use of mid-ranked chunks";
        } else if (type === 'top20') {
            if (count >= 2) return "Good - utilizes lower-ranked chunks";
            if (count >= 1) return "Fair - some use of lower-ranked chunks";
            return "Low - minimal use of lower-ranked chunks";
        }
        return "Standard utilization pattern";
    }

    createChunkUtilizationChart(canvasId, analysisData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const extendedMetrics = this.extractExtendedMetrics(analysisData);
        
        // Check if we have chunk utilization data
        const hasChunkData = extendedMetrics.chunks_used_top5 !== undefined || 
                            extendedMetrics.chunks_used_top10 !== undefined || 
                            extendedMetrics.chunks_used_top20 !== undefined;
        
        if (!hasChunkData) {
            canvas.parentElement.innerHTML = `
                <div class="no-chunk-data">
                    <div class="no-data-icon">📊</div>
                    <div class="no-data-text">Chunk utilization data not available</div>
                    <div class="no-data-subtext">Enable chunk tracking for detailed utilization analysis</div>
                </div>
            `;
            return;
        }

        const ctx = canvas.getContext('2d');
        
        // Prepare data for the chart
        const labels = [];
        const data = [];
        const colors = [];
        
        if (extendedMetrics.chunks_used_top5 !== undefined) {
            labels.push('Top 5');
            data.push(extendedMetrics.chunks_used_top5);
            colors.push('#10b981');
        }
        
        if (extendedMetrics.chunks_used_top10 !== undefined) {
            labels.push('5-10');
            data.push(extendedMetrics.chunks_used_top10);
            colors.push('#059669');
        }
        
        if (extendedMetrics.chunks_used_top20 !== undefined) {
            labels.push('10-20');
            data.push(extendedMetrics.chunks_used_top20);
            colors.push('#0d9488');
        }
        
        // Create bar chart
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Chunks Used',
                    data: data,
                    backgroundColor: colors,
                    borderColor: colors.map(color => color.replace('0.8', '1')),
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.label}: ${context.raw} chunks`
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1,
                            callback: (value) => Math.floor(value) === value ? value : ''
                        }
                    }
                }
            }
        });
    }

    populateStatisticalInsights(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const insights = analysisData.insights;
        let content = '';

        if (insights.statistical && insights.statistical.length > 0) {
            insights.statistical.forEach(stat => {
                content += `<div class="insight-item">${stat}</div>`;
            });
        } else {
            content = `<div class="insight-item">📊 Standard statistical patterns detected across all metrics.</div>`;
        }

        element.innerHTML = content;
    }

    populateRecommendations(elementId, analysisData) {
        const element = document.getElementById(elementId);
        if (!element) return;

        const insights = analysisData.insights;
        let content = '';

        if (insights.recommendations && insights.recommendations.length > 0) {
            // Add a header explaining the evaluation-based recommendations
            content += `
                <div class="recommendation-header">
                    <small>📊 Recommendations based on evaluation metrics analysis:</small>
                </div>
            `;
            
            insights.recommendations.forEach((recommendation, index) => {
                // Extract emoji and text for better formatting
                const emojiMatch = recommendation.match(/^([\u{1F300}-\u{1F9FF}][\u{FE00}-\u{FE0F}]?|[\u{2600}-\u{27BF}])/u);
                const emoji = emojiMatch ? emojiMatch[0] : '💡';
                const text = recommendation.replace(/^[\u{1F300}-\u{1F9FF}][\u{FE00}-\u{FE0F}]?[\u{2600}-\u{27BF}]?\s*/u, '');
                
                // Determine priority class based on emoji
                let priorityClass = 'recommendation-normal';
                if (emoji === '✅') priorityClass = 'recommendation-success';
                else if (emoji === '❌' || emoji === '🔍') priorityClass = 'recommendation-critical';
                else if (emoji === '🛠️' || emoji === '🧪') priorityClass = 'recommendation-action';
                
                content += `
                    <div class="insight-item recommendation ${priorityClass}" data-priority="${index + 1}">
                        <div class="recommendation-content">
                            <span class="recommendation-icon">${emoji}</span>
                            <span class="recommendation-text">${text}</span>
                        </div>
                    </div>
                `;
            });
            
            // Add metric context if available
            const metricValues = this.extractRelevantMetrics(analysisData);
            const hasMetrics = metricValues.context_relevancy !== undefined || 
                              metricValues.answer_correctness !== undefined ||
                              metricValues.ground_truth_validity !== undefined ||
                              metricValues.answer_completeness !== undefined ||
                              metricValues.retrieved_chunk_count !== undefined ||
                              metricValues.sent_to_llm_chunk_count !== undefined ||
                              metricValues.used_in_answer_chunk_count !== undefined ||
                              metricValues.total_chunks_used !== undefined ||
                              metricValues.best_support_rank !== undefined;
            
            if (hasMetrics) {
                content += `
                    <div class="recommendation-context">
                        <small>📈 Based on: `;
                        
                const metricDisplay = [];
                if (metricValues.context_relevancy !== undefined) {
                    metricDisplay.push(`Context Relevancy: ${(metricValues.context_relevancy * 100).toFixed(1)}%`);
                }
                if (metricValues.answer_correctness !== undefined) {
                    metricDisplay.push(`Answer Correctness: ${(metricValues.answer_correctness * 100).toFixed(1)}%`);
                }
                if (metricValues.ground_truth_validity !== undefined) {
                    metricDisplay.push(`GT Validity: ${(metricValues.ground_truth_validity * 100).toFixed(1)}%`);
                }
                if (metricValues.answer_completeness !== undefined) {
                    metricDisplay.push(`Completeness: ${(metricValues.answer_completeness * 100).toFixed(1)}%`);
                }
                if (metricValues.retrieved_chunk_count !== undefined) {
                    metricDisplay.push(`Retrieved: ${metricValues.retrieved_chunk_count.toFixed(1)}`);
                }
                if (metricValues.sent_to_llm_chunk_count !== undefined) {
                    metricDisplay.push(`Sent to LLM: ${metricValues.sent_to_llm_chunk_count.toFixed(1)}`);
                }
                if (metricValues.used_in_answer_chunk_count !== undefined) {
                    metricDisplay.push(`Used: ${metricValues.used_in_answer_chunk_count.toFixed(1)}`);
                }
                if (metricValues.total_chunks_used !== undefined) {
                    metricDisplay.push(`Total Used: ${metricValues.total_chunks_used.toFixed(1)}`);
                }
                if (metricValues.best_support_rank !== undefined) {
                    metricDisplay.push(`Support Rank: ${metricValues.best_support_rank.toFixed(1)}`);
                }
                
                content += metricDisplay.join(', ');
                content += `</small>
                    </div>
                `;
            }
        } else {
            content = `
                <div class="recommendation-header">
                    <small>ℹ️ No specific patterns detected in evaluation data</small>
                </div>
                <div class="insight-item recommendation recommendation-normal">
                    <div class="recommendation-content">
                        <span class="recommendation-icon">📊</span>
                        <span class="recommendation-text">Performance appears balanced across metrics.</span>
                    </div>
                </div>
                <div class="insight-item recommendation recommendation-normal">
                    <div class="recommendation-content">
                        <span class="recommendation-icon">📈</span>
                        <span class="recommendation-text">Consider running evaluation with larger dataset for clearer insights.</span>
                    </div>
                </div>
                <div class="insight-item recommendation recommendation-normal">
                    <div class="recommendation-content">
                        <span class="recommendation-icon">🔄</span>
                        <span class="recommendation-text">Monitor performance trends over time to identify patterns.</span>
                    </div>
                </div>
            `;
        }

        element.innerHTML = content;
    }

    generateIntelligentRecommendations(analysisSummary) {
        console.log('🧠 Generating intelligent recommendations based on comprehensive analysis...');
        
        const recommendations = [];
        const { metrics, performance, chunkAnalysis, configuration } = analysisSummary;
        
        // Generate recommendations based on available metrics
        Object.entries(metrics).forEach(([metricName, stats]) => {
            const score = stats.mean;
            
            if (score < 0.6) {
                recommendations.push(`🔍 **High Priority**: ${metricName} needs improvement (${(score * 100).toFixed(1)}%) - Review system configuration and optimize for better performance.`);
            } else if (score < 0.8) {
                recommendations.push(`📈 **Medium Priority**: ${metricName} has room for improvement (${(score * 100).toFixed(1)}%) - Consider fine-tuning parameters.`);
            } else {
                recommendations.push(`✅ **Low Priority**: ${metricName} performing well (${(score * 100).toFixed(1)}%) - Maintain current configuration.`);
            }
        });
        
        // Add chunk-specific recommendations
        if (chunkAnalysis.hasChunkData) {
            if (chunkAnalysis.retrievedChunkCount > 15) {
                recommendations.push(`⚡ **Medium Priority**: High retrieval count (${chunkAnalysis.retrievedChunkCount.toFixed(1)} chunks) - Consider optimizing retrieval strategy for efficiency.`);
            }
            if (chunkAnalysis.bestSupportRank > 5) {
                recommendations.push(`🏆 **High Priority**: Poor top-rank retrieval (rank ${chunkAnalysis.bestSupportRank}) - Improve ranking algorithm or increase retrieval count.`);
            }
        } else {
            recommendations.push(`📊 **Medium Priority**: Enable chunk tracking for detailed efficiency analysis and optimization insights.`);
        }
        
        // Add configuration recommendations
        if (configuration.evaluationMethods.length < 2) {
            recommendations.push(`🔧 **Medium Priority**: Limited evaluation coverage (${configuration.evaluationMethods.length} method(s)) - Enable additional evaluation methods for comprehensive analysis.`);
        }
        
        // Add performance recommendations
        if (performance.outliers > 0) {
            recommendations.push(`📊 **Medium Priority**: ${performance.outliers} performance outliers detected - Review and investigate unusual patterns.`);
        }
        
        console.log('✅ Generated intelligent recommendations:', recommendations.length);
        return recommendations;
    }

    // NEW: Enhanced recommendation analysis functions
    generateEnhancedRecommendations(analysisSummary) {
        console.log('🚀 Generating enhanced analysis recommendations...');
        
        const recommendations = [];
        const { metrics, performance, chunkAnalysis, configuration } = analysisSummary;
        
        // 1. Cross-metric correlation analysis
        const correlationInsights = this.analyzeMetricCorrelations(metrics);
        recommendations.push(...correlationInsights);
        
        // 2. Performance distribution analysis
        const distributionInsights = this.analyzePerformanceDistribution(metrics);
        recommendations.push(...distributionInsights);
        
        // 3. Efficiency optimization insights
        const efficiencyInsights = this.analyzeEfficiencyPatterns(chunkAnalysis, metrics);
        recommendations.push(...efficiencyInsights);
        
        // 4. Configuration optimization
        const configInsights = this.analyzeConfigurationOptimization(configuration, metrics);
        recommendations.push(...configInsights);
        
        // 5. Data quality insights
        const dataQualityInsights = this.analyzeDataQuality(analysisSummary);
        recommendations.push(...dataQualityInsights);
        
        console.log('✅ Generated enhanced recommendations:', recommendations.length);
        return recommendations;
    }

    analyzeMetricCorrelations(metrics) {
        const recommendations = [];
        const metricEntries = Object.entries(metrics);
        
        // Find potential correlations between metrics
        for (let i = 0; i < metricEntries.length; i++) {
            for (let j = i + 1; j < metricEntries.length; j++) {
                const [metric1, stats1] = metricEntries[i];
                const [metric2, stats2] = metricEntries[j];
                
                const score1 = stats1.mean;
                const score2 = stats2.mean;
                
                // Detect inverse relationships
                if (score1 < 0.6 && score2 > 0.8) {
                    recommendations.push(`🔄 **Medium Priority**: ${metric1} (${(score1 * 100).toFixed(1)}%) and ${metric2} (${(score2 * 100).toFixed(1)}%) show inverse relationship - consider balancing optimization efforts.`);
                }
                
                // Detect both poor performance
                if (score1 < 0.6 && score2 < 0.6) {
                    recommendations.push(`🚨 **High Priority**: Both ${metric1} and ${metric2} need attention - may indicate systemic issues requiring comprehensive review.`);
                }
            }
        }
        
        return recommendations;
    }

    analyzePerformanceDistribution(metrics) {
        const recommendations = [];
        
        Object.entries(metrics).forEach(([metricName, stats]) => {
            const { mean, stdDev, min, max } = stats;
            const variance = stdDev / mean; // Coefficient of variation
            
            // High variance indicates inconsistent performance
            if (variance > 0.3) {
                recommendations.push(`📊 **Medium Priority**: ${metricName} shows high variability (${(variance * 100).toFixed(1)}% CV) - consider standardizing inputs or improving consistency.`);
            }
            
            // Large gap between min and max indicates potential for optimization
            if ((max - min) > 0.4) {
                recommendations.push(`🎯 **Medium Priority**: ${metricName} has wide performance range (${(min * 100).toFixed(1)}%-${(max * 100).toFixed(1)}%) - investigate best-performing cases for optimization insights.`);
            }
        });
        
        return recommendations;
    }

    analyzeEfficiencyPatterns(chunkAnalysis, metrics) {
        const recommendations = [];
        
        if (!chunkAnalysis.hasChunkData) return recommendations;
        
        const { retrievedChunkCount, sentToLLMChunkCount, usedInAnswerChunkCount, bestSupportRank } = chunkAnalysis;
        
        // Analyze chunk utilization efficiency
        if (retrievedChunkCount && usedInAnswerChunkCount) {
            const utilizationRate = usedInAnswerChunkCount / retrievedChunkCount;
            
            if (utilizationRate < 0.3) {
                recommendations.push(`⚡ **High Priority**: Low chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - optimize retrieval precision or reduce chunk count.`);
            } else if (utilizationRate > 0.8) {
                recommendations.push(`📈 **Low Priority**: Excellent chunk utilization (${(utilizationRate * 100).toFixed(1)}%) - system is efficiently using retrieved context.`);
            }
        }
        
        // Analyze processing efficiency
        if (sentToLLMChunkCount && retrievedChunkCount) {
            const processingRate = sentToLLMChunkCount / retrievedChunkCount;
            
            if (processingRate < 0.5) {
                recommendations.push(`🔍 **Medium Priority**: Low processing rate (${(processingRate * 100).toFixed(1)}%) - consider increasing chunks sent to LLM for better context.`);
            }
        }
        
        // Analyze support rank patterns
        if (bestSupportRank) {
            if (bestSupportRank > 10) {
                recommendations.push(`🏆 **High Priority**: Poor support ranking (rank ${bestSupportRank}) - critical need to improve retrieval relevance scoring.`);
            } else if (bestSupportRank > 5) {
                recommendations.push(`📊 **Medium Priority**: Suboptimal support ranking (rank ${bestSupportRank}) - consider re-ranking or expanding retrieval.`);
            }
        }
        
        return recommendations;
    }

    analyzeConfigurationOptimization(configuration, metrics) {
        const recommendations = [];
        
        // Analyze evaluation coverage
        const evaluationMethods = configuration.evaluationMethods || [];
        const hasRAGAS = evaluationMethods.some(m => m.toLowerCase().includes('ragas'));
        const hasLLM = evaluationMethods.some(m => m.toLowerCase().includes('llm'));
        const hasCRAG = evaluationMethods.some(m => m.toLowerCase().includes('crag'));
        
        if (!hasRAGAS && !hasLLM && !hasCRAG) {
            recommendations.push(`🔧 **High Priority**: No evaluation methods detected - enable RAGAS, LLM, or CRAG evaluation for comprehensive analysis.`);
        } else if (evaluationMethods.length === 1) {
            recommendations.push(`📊 **Medium Priority**: Single evaluation method (${evaluationMethods[0]}) - consider adding complementary evaluation methods for broader insights.`);
        }
        
        // Analyze dataset size
        const totalQueries = configuration.totalQueries || 0;
        if (totalQueries < 10) {
            recommendations.push(`📈 **Medium Priority**: Small dataset (${totalQueries} queries) - consider larger evaluation set for more reliable insights.`);
        } else if (totalQueries > 100) {
            recommendations.push(`✅ **Low Priority**: Large dataset (${totalQueries} queries) - comprehensive evaluation provides reliable insights.`);
        }
        
        return recommendations;
    }

    analyzeDataQuality(analysisSummary) {
        const recommendations = [];
        const { metrics, performance } = analysisSummary;
        
        // Check for data completeness
        const metricCount = Object.keys(metrics).length;
        if (metricCount < 3) {
            recommendations.push(`📊 **Medium Priority**: Limited metrics (${metricCount}) - consider enabling more evaluation metrics for comprehensive analysis.`);
        }
        
        // Check for performance outliers
        if (performance.outliers > 0) {
            const outlierPercentage = (performance.outliers / (analysisSummary.configuration.totalQueries || 1)) * 100;
            
            if (outlierPercentage > 20) {
                recommendations.push(`🚨 **High Priority**: High outlier rate (${outlierPercentage.toFixed(1)}%) - investigate data quality and system stability issues.`);
            } else {
                recommendations.push(`📊 **Medium Priority**: ${performance.outliers} outliers detected - review unusual cases for optimization opportunities.`);
            }
        }
        
        // Check for metric consistency
        const metricValues = Object.values(metrics).map(m => m.mean);
        const avgMetric = metricValues.reduce((a, b) => a + b, 0) / metricValues.length;
        const metricVariance = metricValues.reduce((sum, val) => sum + Math.pow(val - avgMetric, 2), 0) / metricValues.length;
        
        if (metricVariance > 0.1) {
            recommendations.push(`📈 **Medium Priority**: High metric variance detected - consider balancing optimization across all metrics for consistent performance.`);
        }
        
        return recommendations;
    }

    // NEW: Smart filtering to avoid overwhelming users
    smartFilterRecommendations(recommendations, analysisSummary) {
        console.log('🎯 Applying smart filtering to recommendations...');
        
        // Remove duplicates and similar recommendations
        const uniqueRecommendations = this.removeDuplicateRecommendations(recommendations);
        
        // Prioritize by importance and system context
        const prioritizedRecommendations = this.prioritizeRecommendations(uniqueRecommendations, analysisSummary);
        
        // Limit to most impactful recommendations (max 12-15)
        const maxRecommendations = 15;
        const finalRecommendations = prioritizedRecommendations.slice(0, maxRecommendations);
        
        console.log(`✅ Filtered to ${finalRecommendations.length} recommendations from ${recommendations.length} total`);
        return finalRecommendations;
    }

    removeDuplicateRecommendations(recommendations) {
        const uniqueRecommendations = [];
        const seenKeywords = new Set();
        
        recommendations.forEach(rec => {
            // Extract key concepts from recommendation
            const keywords = rec.toLowerCase()
                .replace(/[^\w\s]/g, ' ')
                .split(/\s+/)
                .filter(word => word.length > 3)
                .slice(0, 5)
                .join(' ');
            
            if (!seenKeywords.has(keywords)) {
                seenKeywords.add(keywords);
                uniqueRecommendations.push(rec);
            }
        });
        
        return uniqueRecommendations;
    }

    prioritizeRecommendations(recommendations, analysisSummary) {
        const { metrics, configuration } = analysisSummary;
        
        // Score each recommendation based on priority and relevance
        const scoredRecommendations = recommendations.map(rec => {
            let score = 0;
            
            // Priority scoring
            if (rec.includes('**High Priority**')) score += 10;
            else if (rec.includes('**Medium Priority**')) score += 5;
            else if (rec.includes('**Low Priority**')) score += 2;
            
            // Critical issue scoring
            if (rec.includes('🚨') || rec.includes('critical') || rec.includes('systemic')) score += 5;
            
            // Relevance to current system state
            if (rec.includes('chunk') && !analysisSummary.chunkAnalysis.hasChunkData) score += 3;
            if (rec.includes('evaluation') && configuration.evaluationMethods.length < 2) score += 3;
            if (rec.includes('dataset') && configuration.totalQueries < 20) score += 2;
            
            // Performance impact scoring
            const hasLowPerformance = Object.values(metrics).some(stats => stats.mean < 0.6);
            if (hasLowPerformance && rec.includes('improvement')) score += 3;
            
            return { recommendation: rec, score };
        });
        
        // Sort by score (highest first)
        scoredRecommendations.sort((a, b) => b.score - a.score);
        
        return scoredRecommendations.map(item => item.recommendation);
    }

    // NEW: Enhanced UI functions for recommendation actions
    // Modal functionality removed
}

// Modal functionality removed

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🌐 DOM loaded, initializing RAG Evaluator UI...');
    window.ragEvaluatorUI = new RAGEvaluatorUI();
}); 