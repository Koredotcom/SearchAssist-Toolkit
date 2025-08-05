# RAG Evaluator

Advanced RAG System Performance Evaluation

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

## Installation

1. Install dependencies:
```bash
pip install -r src/requirements.txt
```

2. Configure your API credentials in `src/config/config.json`

3. Start the application:
```bash
python src/routes/app.py
```

The application will be available at `http://localhost:8001`

## Configuration

### Session Management Settings

You can configure session behavior by modifying the SessionManager initialization in `utils/sessionManager.py`:

- `max_age_hours`: How long sessions are kept (default: 24 hours)
- `cleanup_interval_hours`: How often cleanup runs (default: 24 hours)

### Cleanup Scheduler

The cleanup scheduler automatically removes old sessions. You can also manually trigger cleanup:

```python
from utils.cleanup_scheduler import manual_cleanup
cleaned_sessions = manual_cleanup()
```

## Usage

### Web Interface

1. **Access the Application**: Navigate to `http://localhost:8001`
2. **Automatic Session**: A unique session is created automatically
3. **Upload Files**: Upload your Excel files - they're stored securely in your session
4. **Run Evaluation**: Configure and run your evaluation
5. **Download Results**: Download your results - only you have access to them

### API Usage

```python
import requests

# Create a session
response = requests.post('http://localhost:8001/api/create-session')
session_id = response.json()['session_id']

# Run evaluation with session
files = {'excel_file': open('data.xlsx', 'rb')}
data = {
    'config': json.dumps(config),
    'session_id': session_id
}
response = requests.post('http://localhost:8001/api/runeval', files=files, data=data)

# Download results
download_url = f'http://localhost:8001/api/download-results/{session_id}'
response = requests.get(download_url)
```

## Monitoring

### Session Statistics

Get statistics about session usage:

```bash
curl http://localhost:8001/api/session-status/{session_id}
```

### Cleanup Operations

Manually clean up old sessions:

```bash
curl -X POST http://localhost:8001/api/cleanup-old-sessions
```

## Troubleshooting

### Session Issues

- **Session Expired**: If you see session expiration errors, refresh the page to create a new session
- **File Access Denied**: Ensure you're using the correct session ID
- **Download Failures**: Check that your session is still valid and has completed evaluations

### Performance Considerations

- Sessions are stored in memory and persisted to disk
- File cleanup happens automatically but can be triggered manually
- Large numbers of concurrent sessions may require additional monitoring

## License

[Your License Here]
