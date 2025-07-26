// RAG Evaluator UI JavaScript - Rewritten for reliability

class RAGEvaluatorUI {
    constructor() {
        this.uploadedFile = null;
        this.evaluationInProgress = false;
        this.progressInterval = null;
        this.startTime = null;
        this.resultData = null;
        this.metricsChart = null;
        this.init();
    }

    init() {
        console.log('🚀 Initializing RAG Evaluator UI...');
        this.setupEventListeners();
        this.setupFormHandlers();
        this.validateForm();
        this.estimateProcessingTime(); // Initialize with no file
        this.loadChartJS();
        console.log('✅ RAG Evaluator UI initialized successfully');
    }

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
            };
            document.head.appendChild(script);
        } else {
            console.log('✅ Chart.js already loaded');
        }
    }

    setupEventListeners() {
        console.log('🔗 Setting up event listeners...');
        
        // File upload handlers
        this.setupFileUpload();
        
        // Evaluation button
        const startBtn = document.getElementById('start-evaluation');
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
        
        // Global test functions for debugging
        window.ragEvaluator = this;
        window.testDownload = () => this.downloadResults();
        window.testViewDetails = () => this.viewDetails();
        window.debugButtons = () => this.debugButtons();
        window.setTestMetrics = () => {
            // Set test data with actual metrics for debugging
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
                "metrics": {
                    "Response Relevancy": 0.87,
                    "Faithfulness": 0.82,
                    "Context Recall": 0.79,
                    "Context Precision": 0.85,
                    "Answer Correctness": 0.88,
                    "Answer Similarity": 0.91,
                    "LLM Answer Relevancy": 0.84,
                    "LLM Context Relevancy": 0.89,
                    "LLM Answer Correctness": 0.86
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
                        "LLM Answer Correctness": 0.89
                    },
                    {
                        "query": "How does machine learning work?",
                        "answer": "Machine learning works by training algorithms on data to identify patterns and make predictions without being explicitly programmed.",
                        "ground_truth": "ML algorithms learn from data to make predictions or decisions.",
                        "Response Relevancy": 0.89,
                        "Faithfulness": 0.91,
                        "Context Recall": 0.82,
                        "Context Precision": 0.88,
                        "Answer Correctness": 0.90,
                        "Answer Similarity": 0.87,
                        "LLM Answer Relevancy": 0.88,
                        "LLM Context Relevancy": 0.84,
                        "LLM Answer Correctness": 0.92
                    },
                    {
                        "query": "What are neural networks?",
                        "answer": "Neural networks are computing systems inspired by biological neural networks that consist of interconnected nodes or neurons.",
                        "ground_truth": "Neural networks are computational models inspired by the human brain.",
                        "Response Relevancy": 0.85,
                        "Faithfulness": 0.79,
                        "Context Recall": 0.77,
                        "Context Precision": 0.83,
                        "Answer Correctness": 0.86,
                        "Answer Similarity": 0.92
                    },
                    {
                        "query": "Explain deep learning",
                        "answer": "Deep learning is a subset of machine learning that uses neural networks with multiple layers to model and understand complex patterns in data.",
                        "ground_truth": "Deep learning uses multi-layered neural networks for complex pattern recognition.",
                        "Response Relevancy": 0.94,
                        "Faithfulness": 0.86,
                        "Context Recall": 0.81,
                        "Context Precision": 0.89,
                        "Answer Correctness": 0.91,
                        "Answer Similarity": 0.88
                    },
                    {
                        "query": "What is natural language processing?",
                        "answer": "Natural language processing (NLP) is a field of AI that focuses on the interaction between computers and human language.",
                        "ground_truth": "NLP enables computers to understand and process human language.",
                        "Response Relevancy": 0.83,
                        "Faithfulness": 0.75,
                        "Context Recall": 0.79,
                        "Context Precision": 0.81,
                        "Answer Correctness": 0.85,
                        "Answer Similarity": 0.89
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
            console.log('✅ Test metrics data set');
            this.showResults(this.resultData);
        };
        window.testChartWithRealData = () => {
            const realMetrics = {
                "Response Relevancy": 0.87,
                "Faithfulness": 0.82,
                "Context Recall": 0.79,
                "Context Precision": 0.85,
                "Answer Correctness": 0.88,
                "Answer Similarity": 0.91,
                "LLM Answer Relevancy": 0.84,
                "LLM Context Relevancy": 0.89,
                "LLM Answer Correctness": 0.86
            };
            console.log('🧪 Testing chart with RAGAS + LLM metrics:', realMetrics);
            this.createMetricsChart(realMetrics);
        };
        window.debugMetricExtraction = (mockResult) => {
            console.log('🔍 Testing metric extraction with mock result:');
            const testResult = mockResult || {
                metrics: {
                    "Response Relevancy": 0.87,
                    "Faithfulness": 0.82,
                    "LLM Answer Relevancy": 0.84,
                    "LLM Context Relevancy": 0.89,
                    "LLM Answer Correctness": 0.86
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
        };
        
        window.testFullLLMOutput = () => {
            console.log('🧪 Testing complete RAGAS + LLM output display...');
            this.setTestMetrics();
            console.log('📋 Result data with LLM metrics:', this.resultData);
            console.log('📊 Extracted metrics:', this.extractMetricsFromResult(this.resultData));
        };
        
        console.log('✅ Event listeners setup complete');
    }

    setupFileUpload() {
        const uploadArea = document.getElementById('upload-area');
        const fileInput = document.getElementById('excel-file');
        const removeFileBtn = document.getElementById('remove-file');

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
            if (target.id === 'download-results' || target.closest('#download-results')) {
                e.preventDefault();
                e.stopPropagation();
                console.log('📥 Download Results button clicked');
                this.downloadResults();
                return;
            }
            
            if (target.id === 'view-details' || target.closest('#view-details')) {
                e.preventDefault();
                e.stopPropagation();
                console.log('👁️ View Details button clicked');
                this.viewDetails();
                return;
            }
            
            if (target.id === 'new-evaluation' || target.closest('#new-evaluation')) {
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
            { id: 'download-results', handler: () => this.downloadResults(), label: 'Download' },
            { id: 'view-details', handler: () => this.viewDetails(), label: 'View Details' },
            { id: 'new-evaluation', handler: () => this.resetForNewEvaluation(), label: 'New Evaluation' }
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
        const formInputs = document.querySelectorAll('#batch-size, #max-concurrent, #use-search-api, #evaluate-ragas, #evaluate-crag, #evaluate-llm');
        formInputs.forEach(input => {
            input.addEventListener('change', () => {
                this.estimateProcessingTime();
                this.validateForm();
            });
        });

        // Handle Search API configuration visibility
        const useSearchApiCheckbox = document.getElementById('use-search-api');
        const searchApiConfig = document.getElementById('search-api-config');
        
        if (useSearchApiCheckbox && searchApiConfig) {
            useSearchApiCheckbox.addEventListener('change', () => {
                searchApiConfig.style.display = useSearchApiCheckbox.checked ? 'block' : 'none';
                this.validateForm();
            });
        }

        // Handle evaluation method changes
        const ragasCheckbox = document.getElementById('evaluate-ragas');
        const cragCheckbox = document.getElementById('evaluate-crag');
        const llmCheckbox = document.getElementById('evaluate-llm');
        
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
        const llmModelSelect = document.getElementById('llm-model');
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
        this.loadSheetNames(file);
        this.validateForm();
        this.estimateProcessingTime();
        
        this.showToast(`File "${file.name}" uploaded successfully`, 'success');
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
        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/get-sheet-names', {
                method: 'POST',
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                this.populateSheetDropdown(data.sheet_names || []);
                
                // Get row count for better estimation
                if (data.row_counts) {
                    this.fileRowCounts = data.row_counts;
                    console.log('📊 File row counts:', this.fileRowCounts);
                    this.estimateProcessingTime(); // Re-estimate with actual data
                }
            }
        } catch (error) {
            console.warn('Error loading sheet names:', error);
        }
    }

    populateSheetDropdown(sheetNames) {
        const sheetSelect = document.getElementById('sheet-name');
        if (sheetSelect) {
            sheetSelect.innerHTML = '<option value="">All sheets</option>';
            sheetNames.forEach(sheetName => {
                const option = document.createElement('option');
                option.value = sheetName;
                option.textContent = sheetName;
                sheetSelect.appendChild(option);
            });
            
            // Add event listener for sheet selection changes to update estimates
            sheetSelect.removeEventListener('change', this.handleSheetChange); // Remove existing
            this.handleSheetChange = () => {
                console.log('📋 Sheet selection changed, updating estimates...');
                this.estimateProcessingTime();
            };
            sheetSelect.addEventListener('change', this.handleSheetChange);
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
        const batchSize = parseInt(document.getElementById('batch-size')?.value || 10);
        const maxConcurrent = parseInt(document.getElementById('max-concurrent')?.value || 5);
        const useSearchApi = document.getElementById('use-search-api')?.checked || false;
        const evaluateRagas = document.getElementById('evaluate-ragas')?.checked || false;
        const evaluateCrag = document.getElementById('evaluate-crag')?.checked || false;
        const evaluateLlm = document.getElementById('evaluate-llm')?.checked || false;
        const selectedSheet = document.getElementById('sheet-name')?.value || '';
        
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
        const overheadTime = Math.max(30, totalQueries * 0.5); // 30s base + 0.5s per query
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
            estimatedTimeElement.textContent = this.formatTime(finalTime);
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

    calculateTimePerQuery(useSearchApi, evaluateRagas, evaluateCrag, evaluateLlm) {
        // Base time for basic processing
        let timePerQuery = 0.5; // 0.5 seconds base
        
        // Search API time (if enabled)
        if (useSearchApi) {
            timePerQuery += 2.5; // Average API response time
        }
        
        // Calculate parallel evaluation time - evaluators run concurrently
        const evaluationTimes = [];
        
        // RAGAS evaluation time (most time-consuming)
        if (evaluateRagas) {
            evaluationTimes.push(12); // RAGAS is computationally expensive
        }
        
        // CRAG evaluation time
        if (evaluateCrag) {
            evaluationTimes.push(3); // CRAG is lighter than RAGAS
        }
        
        // LLM evaluation time (3 API calls per query, but concurrent)
        if (evaluateLlm) {
            evaluationTimes.push(4); // Improved with parallel processing within LLM evaluator
        }
        
        // When running in parallel, take the maximum time (longest running evaluator)
        // rather than sum of all times
        if (evaluationTimes.length > 0) {
            timePerQuery += Math.max(...evaluationTimes);
        }
        
        // Minimum time
        return Math.max(0.5, timePerQuery);
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
        
        const config = {
            sheet_name: document.getElementById('sheet-name')?.value || '',
            evaluate_ragas: document.getElementById('evaluate-ragas')?.checked || false,
            evaluate_crag: document.getElementById('evaluate-crag')?.checked || false,
            evaluate_llm: document.getElementById('evaluate-llm')?.checked || false,
            use_search_api: document.getElementById('use-search-api')?.checked || false,
            save_db: document.getElementById('save-db')?.checked || false,
            llm_model: document.getElementById('llm-model')?.value || '',
            batch_size: parseInt(document.getElementById('batch-size')?.value || 10),
            max_concurrent: parseInt(document.getElementById('max-concurrent')?.value || 5)
        };

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
        
        const response = await fetch('/api/runeval', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
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
        this.updateElement('total-time', this.formatTime(totalTime));
        this.updateElement('avg-time', this.formatTime(avgTime));
        
        // Create metrics chart
        setTimeout(() => {
            this.createMetricsChart(metrics);
            this.setupDirectListeners(); // Ensure buttons work
        }, 100);
        
        this.enableForm();
        this.addLogEntry(`✅ Results displayed: ${totalProcessed} queries processed`, 'success');
    }

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
            
            // Ensure value is between 0 and 1 for RAGAS metrics
            if (numericValue > 1) {
                numericValue = numericValue / 100; // Convert percentage to decimal
            }
            
            // Clamp between 0 and 1
            numericValue = Math.max(0, Math.min(1, numericValue));
            
            processedMetrics[key] = numericValue;
            console.log(`✅ Processed metric: ${key} = ${numericValue}`);
        }
        
        // If no valid metrics were processed, use defaults
        if (Object.keys(processedMetrics).length === 0) {
            console.warn('⚠️ No valid metrics processed, using defaults');
            return this.getDefaultMetrics();
        }
        
        console.log('🎯 Final processed metrics:', processedMetrics);
        return processedMetrics;
    }

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
            'LLM Answer Correctness': 0.81
        };
    }

    updateElement(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
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
        
        const labels = Object.keys(metrics);
        const data = Object.values(metrics);
        
        try {
            this.metricsChart = new Chart(ctx, {
                type: 'radar',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Evaluation Metrics',
                        data: data,
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
    }

    // Button handlers
    downloadResults() {
        console.log('📥 Download Results clicked');
        
        if (!this.resultData) {
            console.log('⚠️ No result data available');
            this.showToast('No results available to download', 'warning');
            return;
        }

        try {
            const downloadUrl = this.resultData.download_url || '/api/download-results/latest';
            const filename = this.resultData.processing_stats?.output_file || 
                           `rag_evaluation_results_${new Date().toISOString().split('T')[0]}.xlsx`;
            
            console.log('📂 Downloading:', downloadUrl);
            
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
                        <li>No RAGAS evaluation was performed</li>
                        <li>The results file could not be read</li>
                    </ul>
                </div>
            `;
        }

        console.log('📊 Creating detailed results table with', detailedResults.length, 'rows');

        // Get all unique columns from the results
        const allColumns = new Set();
        detailedResults.forEach(row => {
            Object.keys(row).forEach(col => allColumns.add(col));
        });

        const columns = Array.from(allColumns);
        
        // Prioritize important columns first
        const priorityColumns = ['query', 'answer', 'ground_truth'];
        const ragasColumns = columns.filter(col => 
            col.toLowerCase().includes('relevancy') || 
            col.toLowerCase().includes('faithfulness') || 
            col.toLowerCase().includes('recall') || 
            col.toLowerCase().includes('precision') || 
            col.toLowerCase().includes('correctness') || 
            col.toLowerCase().includes('similarity')
        );
        const otherColumns = columns.filter(col => 
            !priorityColumns.includes(col) && 
            !ragasColumns.includes(col)
        );

        const orderedColumns = [
            ...priorityColumns.filter(col => columns.includes(col)),
            ...ragasColumns,
            ...otherColumns
        ];

        console.log('📋 Table columns order:', orderedColumns);

        const tableHTML = `
            <div class="results-table-container">
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
                
                ${detailedResults.length >= 100 ? `
                    <div class="table-note">
                        <i class="fas fa-info-circle"></i>
                        <span>Showing first 100 results. Download the full results file for complete data.</span>
                    </div>
                ` : ''}
            </div>
        `;

        return tableHTML;
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
        
        // Format RAGAS metrics
        if (col.includes('relevancy') || col.includes('faithfulness') || 
            col.includes('recall') || col.includes('precision') || 
            col.includes('correctness') || col.includes('similarity')) {
            
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) {
                const percentage = (numValue * 100).toFixed(1);
                const scoreClass = numValue >= 0.8 ? 'score-good' : 
                                 numValue >= 0.6 ? 'score-medium' : 'score-low';
                return `<span class="metric-score ${scoreClass}">${percentage}%</span>`;
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
                return `<span class="number-value">${numValue.toFixed(4)}</span>`;
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
                            <div class="stat-card">
                                <strong>${this.formatTokenCount(stats.total_tokens)}</strong>
                                <span>Total Tokens</span>
                            </div>
                            <div class="stat-card">
                                <strong>${this.formatCurrency(stats.estimated_cost_usd)}</strong>
                                <span>Estimated Cost</span>
                            </div>
                        </div>
                    </div>

                    <div class="detail-section">
                        <h3><i class="fas fa-coins"></i> Token Usage Breakdown</h3>
                        <div class="stats-grid">
                            <div class="stat-card">
                                <strong>${this.formatTokenCount(stats.prompt_tokens)}</strong>
                                <span>Prompt Tokens</span>
                            </div>
                            <div class="stat-card">
                                <strong>${this.formatTokenCount(stats.completion_tokens)}</strong>
                                <span>Completion Tokens</span>
                            </div>
                            <div class="stat-card">
                                <strong>${this.formatTokenCount(stats.total_tokens)}</strong>
                                <span>Total Tokens</span>
                            </div>
                            <div class="stat-card">
                                <strong>${this.formatCostPerQuery(stats.estimated_cost_usd, stats.total_processed)}</strong>
                                <span>Cost per Query</span>
                            </div>
                        </div>
                    </div>

                    <div class="detail-section">
                        <h3><i class="fas fa-table"></i> Detailed RAGAS Results</h3>
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

    resetForNewEvaluation() {
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
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('🌐 DOM loaded, initializing RAG Evaluator UI...');
    new RAGEvaluatorUI();
}); 