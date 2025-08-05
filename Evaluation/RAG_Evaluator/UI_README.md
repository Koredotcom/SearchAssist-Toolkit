# 🚀 RAG Evaluator Web UI - User Guide

## ✨ Overview

The RAG Evaluator Web UI provides a modern, user-friendly interface for evaluating RAG (Retrieval-Augmented Generation) systems using RAGAS and CRAG metrics. This enhanced version features **asynchronous batch processing** for 3-5x performance improvement and beautiful visualizations.

![RAG Evaluator UI](https://img.shields.io/badge/Version-v2.0-blue) ![Async Processing](https://img.shields.io/badge/Async-Batch%20Processing-green) ![UI](https://img.shields.io/badge/UI-Modern%20Web-purple)

## 🏃‍♂️ Quick Start

### 1. Start the UI Server

```bash
# Option 1: Using the startup script (recommended)
python start_ui.py

# Option 2: Direct FastAPI start
cd src && python routes/app.py
```

### 2. Access the Interface

- **Main UI**: http://localhost:8001
- **API Docs**: http://localhost:8001/api/docs
- **Health Check**: http://localhost:8001/api/health

## 📋 Step-by-Step Usage Guide

### Step 1: Upload Your Excel File 📂

![Upload File](docs/upload-demo.gif)

1. **Drag & Drop**: Simply drag your Excel file (`.xlsx` or `.xls`) onto the upload area
2. **Browse**: Click the upload area to browse and select files
3. **Validation**: The system automatically validates file format and size
4. **Sheet Detection**: Available sheets are automatically detected and listed

**Required Excel Structure:**
```
| query          | ground_truth           | contexts (optional) | answer (optional) |
|----------------|------------------------|-------------------|------------------|
| What is AI?    | AI is artificial...    | ["context1", ...] | AI stands for... |
| How does ML... | Machine learning...    | ["context2", ...] | Machine learning.|
```

### Step 2: Configure Evaluation Settings ⚙️

![Configuration](docs/config-demo.gif)

#### Evaluation Methods
- **✅ RAGAS Evaluation**: Response relevancy, faithfulness, context recall, context precision, answer correctness, semantic similarity
- **✅ CRAG Evaluation**: Accuracy assessment using LLM judgment
- **🔍 Use Search API**: Fetch responses from SearchAssist/XO API
- **💾 Save to Database**: Store results in MongoDB

#### Performance Settings
Choose from preset configurations or customize:

| Preset | Batch Size | Max Concurrent | Best For |
|--------|------------|----------------|----------|
| **🐢 Conservative** | 5 | 2 | Rate-limited APIs, small datasets |
| **⚖️ Balanced** | 10 | 5 | Most use cases (recommended) |
| **🚀 High Performance** | 20 | 10 | Powerful systems, unrestricted APIs |

#### Advanced Options
- **🤖 LLM Model**: Choose from GPT-4o, GPT-4o Mini (OpenAI or Azure)
- **📊 Sheet Selection**: Process specific sheets or all sheets  
- **📧 Email Reports**: Automatically send results via email
- **🔐 API Configuration**: Secure input for SearchAssist/XO and LLM credentials

### Step 3: Run Evaluation ▶️

![Processing](docs/processing-demo.gif)

1. **Validation**: System validates all settings and file structure
2. **Estimation**: Shows estimated processing time and query count
3. **Execution**: Real-time progress tracking with detailed logs
4. **Monitoring**: Track completed queries, elapsed time, and remaining time

**Performance Comparison:**
- **Traditional (Sequential)**: 100 queries = ~5-8 minutes
- **New (Async Batch)**: 100 queries = ~1-2 minutes ⚡

### Step 4: View Results 📊

![Results](docs/results-demo.gif)

#### Summary Dashboard
- **📈 Total Processed**: Number of queries evaluated
- **✅ Success Rate**: Percentage of successful evaluations  
- **⏱️ Performance Metrics**: Total time, average per query
- **📉 Evaluation Scores**: Visual radar chart of RAGAS/CRAG metrics

#### Available Actions
- **💾 Download Results**: Get Excel file with detailed results
- **👁️ View Details**: Explore individual query results
- **🔄 New Evaluation**: Start fresh evaluation

#### Output Structure
```
your_file_evaluation_output_20240315-143022.xlsx
├── Sheet1                 (Main evaluation results)
├── Sheet2                 (Additional sheet results)
├── Processing_Summary     (Success/failure statistics)
├── Processing_Metadata    (Configuration and timing)
└── ERROR_Sheet3          (Detailed error information)
```

## 🎯 Features & Benefits

### 🚀 Performance Improvements
- **3-5x Faster Processing**: Asynchronous batch processing
- **Smart Rate Limiting**: Automatic API throttling
- **Memory Efficient**: Processes large datasets without memory issues
- **Error Isolation**: Failed queries don't stop entire process

### 🎨 User Experience
- **Modern Interface**: Clean, intuitive design
- **Real-time Progress**: Live updates with detailed logs
- **Drag & Drop Upload**: Seamless file handling
- **Mobile Responsive**: Works on all device sizes
- **Toast Notifications**: Instant feedback for all actions

### 📊 Advanced Analytics
- **Radar Chart Visualization**: Beautiful RAGAS metrics display
- **Processing Statistics**: Detailed performance analytics
- **Error Reporting**: Comprehensive error tracking
- **Export Options**: Multiple download formats

### 🛡️ Reliability Features
- **Data Validation**: Input validation at every step
- **Error Recovery**: Graceful handling of failures
- **Backup Creation**: Automatic file backups
- **Fallback Options**: CSV export if Excel fails

## 🔧 Configuration Options

### API Configuration

The system supports multiple API integrations:

```json
{
  "SA": {
    "app_id": "your-searchassist-app-id",
    "client_id": "your-client-id", 
    "client_secret": "your-client-secret",
    "domain": "your-domain.com"
  },
  "UXO": {
    "app_id": "your-uxo-app-id",
    "client_id": "your-client-id",
    "client_secret": "your-client-secret", 
    "domain": "your-domain.com"
  }
}
```

### Performance Tuning

#### For Small Datasets (≤50 queries)
```bash
Batch Size: 5
Max Concurrent: 2
Expected Time: 30-60 seconds
```

#### For Medium Datasets (50-200 queries)  
```bash
Batch Size: 10
Max Concurrent: 5
Expected Time: 1-3 minutes
```

#### For Large Datasets (200+ queries)
```bash
Batch Size: 20
Max Concurrent: 10
Expected Time: 3-10 minutes
```

## 🚨 Troubleshooting

### Common Issues

#### 1. **File Upload Fails**
```
❌ Error: File type not supported
✅ Solution: Use .xlsx or .xls files only
```

#### 2. **Processing Stuck**
```  
❌ Error: Evaluation hangs at X%
✅ Solution: Check API credentials and rate limits
```

#### 3. **High Memory Usage**
```
❌ Error: Out of memory
✅ Solution: Reduce batch_size and max_concurrent
```

#### 4. **API Rate Limits**
```
❌ Error: Too many requests
✅ Solution: Use Conservative preset or reduce concurrency
```

### Performance Optimization

#### For Rate-Limited APIs
- Use **Conservative** preset
- Increase delays between batches
- Monitor API response times

#### For High-Volume Processing
- Use **High Performance** preset
- Ensure stable internet connection
- Monitor system resources

#### For Mixed Workloads
- Use **Balanced** preset (default)
- Monitor progress and adjust if needed
- Consider processing during off-peak hours

## 📈 Advanced Features

### Real-time Monitoring
- Live progress updates
- Detailed processing logs
- Performance metrics
- Error tracking

### Batch Processing Optimization
- Intelligent batching
- Concurrent request management  
- Automatic retry logic
- Memory-efficient processing

### Result Analytics
- Interactive visualizations
- Comparative analysis
- Export capabilities
- Historical tracking

## 🆘 Support

### Getting Help
1. **Check Logs**: Review console output for detailed errors
2. **API Documentation**: Visit `/api/docs` for API details
3. **Health Check**: Use `/api/health` to verify system status
4. **GitHub Issues**: Report bugs and feature requests

### System Requirements
- **Python**: 3.8 or higher
- **Memory**: 4GB RAM minimum, 8GB recommended
- **Storage**: 1GB free space for results
- **Browser**: Modern browser with JavaScript enabled

## 🔄 Updates & Roadmap

### Version 2.0 Features ✅
- Asynchronous batch processing
- Modern web interface
- Real-time progress tracking
- Enhanced error handling
- Performance optimization

### Upcoming Features 🚧
- WebSocket real-time updates
- Advanced filtering options
- Custom evaluation metrics
- API key management interface
- Results comparison tools

---

**🎉 Ready to start? Run `python start_ui.py` and open http://localhost:8001** 