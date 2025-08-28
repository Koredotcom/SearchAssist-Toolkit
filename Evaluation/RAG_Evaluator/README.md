# 🧠 RAG Evaluator

**Advanced Retrieval-Augmented Generation (RAG) System Performance Evaluation Platform**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com/)
[![RAGAS](https://img.shields.io/badge/RAGAS-Latest-purple.svg)](https://github.com/explodinggradients/ragas)
[![Async Processing](https://img.shields.io/badge/Processing-Async%20Batch-orange.svg)]()

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Evaluation Methods](#-evaluation-methods)
- [Quick Start](#-quick-start)
- [Installation & Setup](#-installation--setup)
- [Configuration](#-configuration)
- [Usage Guide](#-usage-guide)
- [Data Format](#-data-format)
- [Output Interpretation](#-output-interpretation)
- [API Reference](#-api-reference)
- [Multi-User Session Management](#-multi-user-session-management)
- [Performance Optimization](#-performance-optimization)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)

## 🎯 Overview

The **RAG Evaluator** is a comprehensive platform for evaluating Retrieval-Augmented Generation (RAG) systems using state-of-the-art metrics and methodologies. It provides both a modern web interface and programmatic API access for assessing the quality, relevance, and accuracy of RAG-based question-answering systems.

### What is RAG Evaluation?

RAG (Retrieval-Augmented Generation) systems combine information retrieval with language generation to answer questions. Evaluating these systems requires specialized metrics that assess:

- **Answer Quality**: How accurate and relevant are the generated responses?
- **Context Relevance**: How well does retrieved context support the answers?
- **Faithfulness**: Are answers grounded in the provided context?
- **Completeness**: Do answers address all aspects of the questions?

## ✨ Key Features

### 🚀 **Performance & Scalability**
- **3-5x Faster Processing** with asynchronous batch processing
- **Smart Rate Limiting** to handle API constraints
- **Memory Efficient** handling of large datasets
- **Concurrent Processing** with configurable batch sizes

### 📊 **Comprehensive Evaluation**
- **RAGAS Metrics**: Response relevancy, faithfulness, context recall/precision, answer correctness
- **CRAG Assessment**: LLM-based accuracy evaluation  
- **LLM Evaluation**: Custom OpenAI/Azure-based assessment
- **Search API Integration** for live response generation

### 🎨 **Modern Web Interface**
- **Drag & Drop File Upload** with automatic validation
- **Real-time Progress Tracking** with detailed logs
- **Beautiful Visualizations** including radar charts
- **Mobile Responsive** design for all devices

### 🔒 **Enterprise Ready**
- **Multi-User Session Management** with secure file isolation
- **API Security** with session validation
- **Automatic Cleanup** of old files and sessions
- **MongoDB Integration** for result persistence

## 🔬 Evaluation Methods

### 1. **RAGAS (Retrieval Augmented Generation Assessment)**

RAGAS provides six key metrics for comprehensive RAG evaluation:

| Metric | Description | Range | Ideal Score |
|--------|-------------|-------|-------------|
| **Response Relevancy** | How relevant is the response to the query | 0-1 | >0.8 |
| **Faithfulness** | Whether the response is grounded in context | 0-1 | >0.9 |
| **Context Recall** | How much relevant context was retrieved | 0-1 | >0.8 |
| **Context Precision** | Precision of retrieved context | 0-1 | >0.8 |
| **Answer Correctness** | Semantic and factual correctness | 0-1 | >0.8 |
| **Answer Similarity** | Semantic similarity to ground truth | 0-1 | >0.7 |

### 2. **CRAG (Comprehensive RAG Assessment Benchmark)**

CRAG evaluates responses using LLM-based judgment:

- **Accuracy Assessment**: Binary correct/incorrect classification
- **Hallucination Detection**: Identifies made-up information
- **Missing Information**: Detects incomplete responses
- **Overall Score**: Combines accuracy, hallucination, and completeness

### 3. **LLM Evaluation (Custom)**

Custom evaluation using OpenAI/Azure OpenAI models:

- **Answer Correctness**: Detailed correctness assessment
- **Answer Relevancy**: Relevance to the original question
- **Context Relevancy**: How well context supports the answer
- **Configurable Prompts**: Customizable evaluation criteria

## 🚀 Quick Start

### 1. **Web Interface (Recommended)**

```bash
# Clone the repository
git clone <repository-url>
cd RAG_Evaluator

# Install dependencies
pip install -r src/requirements.txt

# Start the web interface
python start_ui.py
```

Then open http://localhost:8001 in your browser.

### 2. **Command Line Usage**

```bash
# Run evaluation with Python
cd src
python main.py --file data.xlsx --sheet Sheet1 --ragas --crag
```

### 3. **API Usage**

```python
import requests
import json

# Create session
response = requests.post('http://localhost:8001/api/create-session')
session_id = response.json()['session_id']

# Upload and evaluate
files = {'excel_file': open('data.xlsx', 'rb')}
data = {
    'params': json.dumps({
        'sheet_name': 'Sheet1',
        'evaluate_ragas': True,
        'evaluate_crag': True
    }),
    'session_id': session_id
}
response = requests.post('http://localhost:8001/api/runeval', files=files, data=data)
```

## 🔐 Multi-User Session Management

The RAG Evaluator now includes **user-level file separation** to support multiple concurrent users safely:

### Key Features

- **Unique Session IDs**: Each user gets a unique session ID when they start using the application
- **Isolated File Storage**: Files are stored in session-specific directories (`outputs/session_<session_id>/`)
- **Secure Downloads**: Users can only download their own evaluation results
- **Automatic Cleanup**: Old session files are automatically cleaned up after 24 hours
- **Session Persistence**: Sessions are maintained across page refreshes using localStorage

### Session Management

#### For End Users
1. **Automatic Session Creation**: A unique session is automatically created when you load the application
2. **Session Indicator**: Your session ID is displayed in the header (first 8 characters)
3. **File Isolation**: Your uploaded files and results are completely isolated from other users
4. **Secure Downloads**: Only you can access and download your evaluation results

#### For Administrators
- **Session Monitoring**: View active sessions via `/api/session-status/{session_id}`
- **Manual Cleanup**: Trigger cleanup of old sessions via `/api/cleanup-old-sessions`
- **Session Statistics**: Monitor session usage and storage consumption

### API Endpoints

#### Session Management
- `POST /api/create-session` - Create a new user session
- `GET /api/session-status/{session_id}` - Get session information
- `POST /api/cleanup-old-sessions` - Clean up old sessions (admin)

#### File Operations
- `POST /api/runeval` - Run evaluation (requires session_id)
- `GET /api/download-results/{session_id}` - Download session-specific results

### Directory Structure

```
outputs/
├── session_<uuid1>/
│   ├── input_<session_id>_<filename>.xlsx
│   └── <filename>_evaluation_output_<session_short>_<timestamp>.xlsx
├── session_<uuid2>/
│   ├── input_<session_id>_<filename>.xlsx
│   └── <filename>_evaluation_output_<session_short>_<timestamp>.xlsx
└── sessions.json (session metadata)
```

### Security Features

- **Session Validation**: All operations validate session ownership
- **File Access Control**: Users cannot access files from other sessions
- **IP and User Agent Tracking**: Sessions are associated with client metadata
- **Automatic Expiration**: Sessions older than 24 hours are automatically cleaned up

## 🛠 Installation & Setup

### Prerequisites

- **Python 3.8 or higher**
- **pip** (Python package manager)
- **Git** (for cloning the repository)
- **MongoDB** (optional, for result persistence)

### Step 1: Clone the Repository

```bash
git clone <repository-url>
cd RAG_Evaluator
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv rag-evaluator-env

# Activate virtual environment
# On Windows:
rag-evaluator-env\Scripts\activate
# On macOS/Linux:
source rag-evaluator-env/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r src/requirements.txt
```

### Step 4: Set Up Environment Variables

Create a `.env` file in the project root:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_ORG_ID=your_org_id_here

# Azure OpenAI Configuration (Optional)
AZURE_OPENAI_API_KEY=your_azure_key_here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# MongoDB Configuration (Optional)
MONGO_URL=mongodb://localhost:27017
DB_NAME=rag_evaluator
COLLECTION_NAME=evaluations

# Email Configuration (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### Step 5: Start the Application

```bash
# Option 1: Using the startup script (Recommended)
python start_ui.py

# Option 2: Direct FastAPI start
cd src && python routes/app.py

# Option 3: Using uvicorn directly
uvicorn src.routes.app:app --host 0.0.0.0 --port 8001 --reload
```

The application will be available at `http://localhost:8001`

## ⚙️ Configuration

### Dynamic Configuration System

The RAG Evaluator uses a **dynamic configuration system** that doesn't require static config files. All configurations are created per-session through the web interface or API calls.

### Configuration Options

#### 1. **LLM Provider Configuration**

**OpenAI Configuration:**
```json
{
  "openai": {
    "api_key": "sk-...",
    "org_id": "org-...",
    "model_name": "gpt-4o",
    "embedding_name": "text-embedding-ada-002"
  }
}
```

**Azure OpenAI Configuration:**
```json
{
  "azure": {
    "api_key": "your-azure-key",
    "base_url": "https://your-resource.openai.azure.com/",
    "openai_api_version": "2024-02-15-preview",
    "model_name": "gpt-4o",
    "model_deployment": "gpt-4o-deployment",
    "embedding_name": "text-embedding-ada-002",
    "embedding_deployment": "embedding-deployment"
  }
}
```

#### 2. **Search API Configuration**

**SearchAssist (SA) Configuration:**
```json
{
  "SA": {
    "app_id": "your-searchassist-app-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret",
    "domain": "your-domain.com"
  }
}
```

**XO Platform (UXO) Configuration:**
```json
{
  "UXO": {
    "app_id": "your-xo-app-id",
    "client_id": "your-client-id", 
    "client_secret": "your-client-secret",
    "domain": "your-domain.com"
  }
}
```

#### 3. **Database Configuration**

**MongoDB Setup (Optional):**
```json
{
  "MongoDB": {
    "url": "mongodb://localhost:27017",
    "dbName": "rag_evaluator",
    "collectionName": "evaluations"
  }
}
```

#### 4. **Cost Tracking Configuration**

```json
{
  "cost_of_model": {
    "input": 0.00000015,
    "output": 0.0000006
  }
}
```

### Session Management Settings

Configure session behavior in `utils/sessionManager.py`:

```python
# Session configuration
MAX_AGE_HOURS = 24          # How long sessions are kept
CLEANUP_INTERVAL_HOURS = 24 # How often cleanup runs
BASE_OUTPUT_DIR = "outputs" # Where session files are stored
```

### Performance Tuning

#### Batch Processing Settings

| Setting | Small Dataset | Medium Dataset | Large Dataset |
|---------|---------------|----------------|---------------|
| **Batch Size** | 5 | 10 | 20 |
| **Max Concurrent** | 2 | 5 | 10 |
| **Expected Time** | 30-60s | 1-3min | 3-10min |

#### Memory Optimization

```python
# For memory-constrained environments
BATCH_SIZE = 5
MAX_CONCURRENT = 2
ENABLE_MEMORY_OPTIMIZATION = True
```

## 📖 Usage Guide

### Web Interface (Recommended)

#### 1. **Access the Application**
Navigate to `http://localhost:8001` in your web browser.

#### 2. **Upload Your Data File**
- **Drag & Drop**: Drag your Excel file onto the upload area
- **Browse**: Click to browse and select files
- **Validation**: System validates file format and structure
- **Sheet Selection**: Choose which sheet(s) to evaluate

#### 3. **Configure Evaluation Settings**

**Basic Settings:**
- ✅ **RAGAS Evaluation**: Enable comprehensive RAGAS metrics
- ✅ **CRAG Evaluation**: Enable LLM-based accuracy assessment
- ✅ **LLM Evaluation**: Enable custom OpenAI/Azure evaluation
- 🔍 **Use Search API**: Enable live response generation

**Performance Settings:**
- **Preset Options**: Conservative, Balanced, High Performance
- **Custom Settings**: Batch size and concurrency limits
- **Model Selection**: Choose GPT-4o, GPT-4o Mini, or Azure models

**Advanced Options:**
- **Database Storage**: Save results to MongoDB
- **Email Reports**: Automatic email delivery
- **API Credentials**: Configure SearchAssist/XO and LLM APIs

#### 4. **Monitor Evaluation Progress**
- **Real-time Updates**: Live progress tracking
- **Detailed Logs**: Step-by-step processing information
- **Performance Metrics**: Processing speed and success rates
- **Error Handling**: Automatic retry and error reporting

#### 5. **Download and Analyze Results**
- **Summary Dashboard**: Overview of evaluation metrics
- **Detailed Results**: Individual query assessments
- **Excel Export**: Comprehensive results in Excel format
- **Visualization**: Radar charts and performance graphs

### Command Line Interface

#### Basic Evaluation
```bash
cd src
python main.py \
  --file ../data/sample.xlsx \
  --sheet "Sheet1" \
  --ragas \
  --crag
```

#### Advanced Evaluation with Search API
```bash
python main.py \
  --file ../data/sample.xlsx \
  --sheet "Sheet1" \
  --ragas \
  --crag \
  --llm \
  --use-search-api \
  --llm-model "openai" \
  --batch-size 10 \
  --max-concurrent 5
```

### Programmatic API Usage

#### Complete Evaluation Workflow
```python
import requests
import json
import time

# Step 1: Create a session
response = requests.post('http://localhost:8001/api/create-session')
session_data = response.json()
session_id = session_data['session_id']
print(f"Created session: {session_id}")

# Step 2: Get sheet names from file
with open('data.xlsx', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:8001/api/get-sheet-names', files=files)
    sheets = response.json()['sheet_names']
    print(f"Available sheets: {sheets}")

# Step 3: Configure evaluation parameters
params = {
    'sheet_name': sheets[0],
    'evaluate_ragas': True,
    'evaluate_crag': True,
    'evaluate_llm': False,
    'use_search_api': False,
    'llm_model': 'openai',
    'save_db': False,
    'batch_size': 10,
    'max_concurrent': 5
}

# Step 4: Upload file and run evaluation
with open('data.xlsx', 'rb') as f:
    files = {'excel_file': f}
    data = {
        'params': json.dumps(params),
        'session_id': session_id,
        'config': json.dumps({
            "openai": {
                "api_key": "sk-...",
                "model_name": "gpt-4o"
            }
        })
    }
    
    response = requests.post('http://localhost:8001/api/runeval', files=files, data=data)
    result = response.json()
    print(f"Evaluation result: {result}")

# Step 5: Check evaluation status (if async)
if 'evaluation_id' in result:
    evaluation_id = result['evaluation_id']
    
    # Poll for completion
    while True:
        response = requests.get(f'http://localhost:8001/api/evaluation-status/{evaluation_id}')
        status = response.json()
        
        if status['status'] == 'completed':
            print("Evaluation completed!")
            break
        elif status['status'] == 'failed':
            print(f"Evaluation failed: {status['error']}")
            break
        else:
            print(f"Status: {status['status']}, Progress: {status.get('progress', 0)}%")
            time.sleep(5)

# Step 6: Download results
download_url = f'http://localhost:8001/api/download-results/{session_id}'
response = requests.get(download_url)

if response.status_code == 200:
    with open('evaluation_results.xlsx', 'wb') as f:
        f.write(response.content)
    print("Results downloaded successfully!")
else:
    print(f"Download failed: {response.text}")
```

## 📊 Data Format

### Required Excel Structure

Your Excel file must contain the following columns:

#### Minimum Required Columns
```
| query          | ground_truth           |
|----------------|------------------------|
| What is AI?    | AI is artificial...    |
| How does ML... | Machine learning...    |
```

#### Full Structure (All Evaluation Methods)
```
| query          | ground_truth           | context                    | answer              |
|----------------|------------------------|----------------------------|---------------------|
| What is AI?    | AI is artificial...    | ["AI context info..."]     | AI stands for...    |
| How does ML... | Machine learning...    | ["ML context info..."]     | Machine learning... |
```

### Column Specifications

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| **query** | String | ✅ **Yes** | The question or prompt to evaluate |
| **ground_truth** | String | ✅ **Yes** | The correct/expected answer |
| **context** | String/List | ⚠️ **RAGAS** | Retrieved context (JSON list format) |
| **answer** | String | ⚠️ **No Search API** | Generated response (auto-generated if using Search API) |

### Context Format Examples

**Single Context:**
```json
["This is the relevant context for the question."]
```

**Multiple Contexts:**
```json
[
  "First piece of relevant context.",
  "Second piece of relevant context.",
  "Third piece of relevant context."
]
```

**Empty Context:**
```json
[]
```

### Data Quality Guidelines

#### ✅ **Best Practices**
- **Clear Questions**: Write specific, unambiguous queries
- **Comprehensive Answers**: Provide complete ground truth responses
- **Relevant Context**: Include only context that supports the answer
- **Consistent Format**: Maintain uniform data structure across rows
- **Quality Control**: Review data for accuracy before evaluation

#### ❌ **Common Issues to Avoid**
- **Vague Questions**: "Tell me about X" (too broad)
- **Incomplete Answers**: Single-word responses for complex questions
- **Irrelevant Context**: Context that doesn't support the answer
- **Malformed JSON**: Invalid JSON in context fields
- **Mixed Languages**: Inconsistent language across columns

## 📈 Output Interpretation

### Understanding Your Results

#### RAGAS Metrics Interpretation

| Metric | Range | Good Score | Interpretation |
|--------|-------|------------|----------------|
| **Response Relevancy** | 0-1 | >0.8 | How well the response addresses the question |
| **Faithfulness** | 0-1 | >0.9 | Whether the response contradicts the context |
| **Context Recall** | 0-1 | >0.8 | Coverage of relevant information in context |
| **Context Precision** | 0-1 | >0.8 | Precision of retrieved context |
| **Answer Correctness** | 0-1 | >0.8 | Factual and semantic correctness |
| **Answer Similarity** | 0-1 | >0.7 | Semantic similarity to ground truth |

#### CRAG Metrics Interpretation

| Metric | Range | Description |
|--------|-------|-------------|
| **Score** | -1, 0, 1 | Overall assessment (-1: incorrect, 0: neutral, 1: correct) |
| **Accuracy** | 0-1 | Percentage of correct responses |
| **Hallucination** | 0-1 | Percentage of responses with made-up information |
| **Missing** | 0-1 | Percentage of responses with missing information |

#### LLM Evaluation Metrics

| Metric | Range | Description |
|--------|-------|-------------|
| **Answer Correctness** | 0-1 | Detailed correctness assessment |
| **Answer Relevancy** | 0-1 | Relevance to the original question |
| **Context Relevancy** | 0-1 | How well context supports the answer |

### Result File Structure

Your downloaded Excel file contains multiple sheets:

```
evaluation_results.xlsx
├── Main_Results          # Combined evaluation results
├── RAGAS_Results         # Detailed RAGAS metrics
├── CRAG_Results          # CRAG assessment details
├── LLM_Results           # LLM evaluation details (if enabled)
├── Processing_Summary    # Success/failure statistics
├── Processing_Metadata   # Configuration and timing info
└── Error_Log            # Detailed error information
```

### Key Performance Indicators

#### Overall System Health
- **Success Rate**: >90% (high-quality data and configuration)
- **Average Processing Time**: <2 seconds per query
- **Error Rate**: <5% (well-configured APIs)

#### Quality Thresholds
- **Excellent**: All RAGAS metrics >0.8
- **Good**: Most RAGAS metrics >0.7
- **Needs Improvement**: Multiple metrics <0.6

## 🔗 API Reference

### Authentication
All API calls require a valid session ID for security and file isolation.

### Core Endpoints

#### **Session Management**

**Create Session**
```http
POST /api/create-session
Content-Type: application/json

{
  "client_info": {
    "user_agent": "string",
    "ip": "string"
  }
}
```

Response:
```json
{
  "session_id": "uuid-string",
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2024-01-16T10:30:00Z"
}
```

**Session Status**
```http
GET /api/session-status/{session_id}
```

Response:
```json
{
  "session_id": "uuid-string",
  "status": "active",
  "created_at": "2024-01-15T10:30:00Z",
  "last_accessed": "2024-01-15T11:00:00Z",
  "file_count": 3,
  "total_size_mb": 15.2
}
```

#### **File Operations**

**Get Sheet Names**
```http
POST /api/get-sheet-names
Content-Type: multipart/form-data

file: <excel_file>
```

Response:
```json
{
  "status": "success",
  "sheet_names": ["Sheet1", "Sheet2"],
  "total_sheets": 2,
  "row_counts": {"Sheet1": 100, "Sheet2": 50},
  "total_rows": 150
}
```

**Run Evaluation**
```http
POST /api/runeval
Content-Type: multipart/form-data

excel_file: <file>
params: <json_string>
config: <json_string>
session_id: <string>
```

Request Parameters:
```json
{
  "params": {
    "sheet_name": "Sheet1",
    "evaluate_ragas": true,
    "evaluate_crag": true,
    "evaluate_llm": false,
    "use_search_api": false,
    "llm_model": "openai",
    "save_db": false,
    "batch_size": 10,
    "max_concurrent": 5
  },
  "config": {
    "openai": {
      "api_key": "sk-...",
      "model_name": "gpt-4o"
    }
  }
}
```

Response:
```json
{
  "status": "success",
  "message": "Evaluation completed",
  "total_processed": 100,
  "success_count": 95,
  "error_count": 5,
  "processing_time_seconds": 45.2,
  "download_url": "/api/download-results/{session_id}"
}
```

**Download Results**
```http
GET /api/download-results/{session_id}
```

Response: Excel file download

#### **Health & Monitoring**

**Health Check**
```http
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "uptime_seconds": 3600,
  "active_sessions": 5
}
```

**System Statistics**
```http
GET /api/stats
```

Response:
```json
{
  "total_evaluations": 1250,
  "total_queries_processed": 125000,
  "average_processing_time": 1.8,
  "success_rate": 0.94
}
```

### Error Responses

All endpoints return consistent error responses:

```json
{
  "error": "Error description",
  "error_code": "VALIDATION_ERROR",
  "details": {
    "field": "specific error details"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Common Error Codes:
- `VALIDATION_ERROR`: Input validation failed
- `SESSION_EXPIRED`: Session is no longer valid
- `FILE_NOT_FOUND`: Requested file doesn't exist
- `API_ERROR`: External API call failed
- `PROCESSING_ERROR`: Evaluation processing failed

## ⚡ Performance Optimization

### Recommended Settings by Dataset Size

#### Small Datasets (≤50 queries)
```json
{
  "batch_size": 5,
  "max_concurrent": 2,
  "expected_time": "30-60 seconds",
  "memory_usage": "Low"
}
```

#### Medium Datasets (50-200 queries)
```json
{
  "batch_size": 10,
  "max_concurrent": 5,
  "expected_time": "1-3 minutes",
  "memory_usage": "Medium"
}
```

#### Large Datasets (200+ queries)
```json
{
  "batch_size": 20,
  "max_concurrent": 10,
  "expected_time": "3-10 minutes",
  "memory_usage": "High"
}
```

### API Rate Limiting

Different APIs have different rate limits. Adjust settings accordingly:

| API Provider | Recommended Batch Size | Max Concurrent |
|--------------|------------------------|----------------|
| **OpenAI GPT-4** | 5-10 | 2-3 |
| **Azure OpenAI** | 10-15 | 5-8 |
| **SearchAssist** | 15-20 | 8-10 |
| **XO Platform** | 10-15 | 5-8 |

### Memory Optimization

For memory-constrained environments:

```python
# Reduce memory usage
ENABLE_STREAMING = True
BATCH_SIZE = 5
MAX_CONCURRENT = 2
CLEAR_CACHE_INTERVAL = 100  # Clear cache every 100 queries
```

### Performance Monitoring

Monitor these metrics for optimal performance:

- **Processing Speed**: <2 seconds per query
- **Memory Usage**: <4GB for 1000 queries
- **API Success Rate**: >95%
- **Error Recovery Time**: <30 seconds

## 🔧 Troubleshooting

### Common Issues and Solutions

#### 1. **Installation Problems**

**Issue**: `pip install` fails with dependency conflicts
```bash
# Solution: Use virtual environment
python -m venv rag-evaluator-env
source rag-evaluator-env/bin/activate  # Linux/Mac
rag-evaluator-env\Scripts\activate     # Windows
pip install -r src/requirements.txt
```

**Issue**: Missing system dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-dev build-essential

# macOS
xcode-select --install

# Windows
# Install Microsoft C++ Build Tools
```

#### 2. **Configuration Issues**

**Issue**: "API key not found" error
```bash
# Check environment variables
echo $OPENAI_API_KEY

# Or set in .env file
OPENAI_API_KEY=sk-your-key-here
```

**Issue**: "Invalid API configuration"
- Verify API credentials are correct
- Check API endpoint URLs
- Ensure sufficient API quotas/credits

#### 3. **File Upload Problems**

**Issue**: "File format not supported"
- Use `.xlsx` or `.xls` files only
- Ensure file is not corrupted
- Check file size limits (<100MB)

**Issue**: "Missing required columns"
- Verify `query` and `ground_truth` columns exist
- Check column names for exact spelling
- Remove empty rows from Excel file

#### 4. **Evaluation Failures**

**Issue**: Evaluation hangs or times out
```python
# Reduce batch size and concurrency
{
  "batch_size": 5,
  "max_concurrent": 2
}
```

**Issue**: High error rates
- Check API rate limits
- Verify network connectivity
- Review API credentials
- Check input data quality

#### 5. **Performance Issues**

**Issue**: Slow processing
- Use performance presets (High Performance)
- Increase batch size and concurrency
- Check system resources (CPU, memory)
- Use faster internet connection

**Issue**: Out of memory errors
```python
# Memory optimization settings
{
  "batch_size": 3,
  "max_concurrent": 1,
  "enable_memory_optimization": True
}
```

#### 6. **Session Management Issues**

**Issue**: Session expired errors
- Refresh the web page to create new session
- Check session timeout settings
- Verify session ID in API calls

**Issue**: File access denied
- Use correct session ID
- Check file permissions
- Verify session is still active

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Set environment variable
export DEBUG_MODE=true

# Or in .env file
DEBUG_MODE=true
LOG_LEVEL=DEBUG
```

### Getting Help

1. **Check Logs**: Review console output for detailed errors
2. **API Documentation**: Visit `/api/docs` for interactive API testing
3. **Health Check**: Use `/api/health` to verify system status
4. **GitHub Issues**: Report bugs with detailed error messages
5. **Community Support**: Join our Discord/Slack for community help

### System Requirements

#### Minimum Requirements
- **OS**: Windows 10, macOS 10.14, Ubuntu 18.04+
- **Python**: 3.8+
- **RAM**: 4GB
- **Storage**: 2GB free space
- **Network**: Stable internet connection

#### Recommended Requirements
- **RAM**: 8GB+
- **Storage**: 10GB free space
- **CPU**: 4+ cores
- **Network**: High-speed internet (for API calls)

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd RAG_Evaluator

# Install development dependencies
pip install -r src/requirements.txt
pip install -r dev-requirements.txt

# Run tests
pytest tests/

# Start development server
python start_ui.py --reload
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**🎉 Ready to start evaluating your RAG system? Run `python start_ui.py` and open http://localhost:8001**
