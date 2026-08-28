#!/usr/bin/env python3
# Prevent Python from creating .pyc files
import sys
sys.dont_write_bytecode = True

"""
RAG Evaluator UI Startup Script
===============================

This script starts the RAG Evaluator web interface with the enhanced UI.

Usage:
    python start_ui.py

The UI will be available at:
    - Main Interface: http://localhost:8001
    - API Documentation: http://localhost:8001/api/docs
    - Interactive API: http://localhost:8001/api/redoc

Features:
    - Modern drag & drop file upload
    - Real-time progress tracking
    - Performance optimization settings
    - Beautiful result visualization
    - Downloadable reports
"""

import os
import sys
import webbrowser
import time
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    required_packages = [
        'fastapi',
        'uvicorn',
        'pandas',
        'openpyxl',
        'aiohttp',
        'ragas',
        'openai',
        'langchain_openai',
        'datasets',
        'transformers'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   • {package}")
        
        print("\n💡 Installation options:")
        print("   1. Install all requirements:")
        print("      pip install -r src/requirements.txt")
        print("\n   2. Install missing packages individually:")
        print(f"      pip install {' '.join(missing_packages)}")
        
        # Provide specific guidance for problematic packages
        if 'ragas' in missing_packages:
            print("\n   💡 For RAGAS: pip install ragas")
        if 'transformers' in missing_packages:
            print("   💡 For Transformers: pip install transformers torch")
        if any(pkg in missing_packages for pkg in ['openai', 'langchain_openai']):
            print("   💡 For OpenAI: pip install openai langchain-openai")
        
        print("\n⚠️  Note: Some packages require additional system dependencies")
        print("   See README.md for detailed installation instructions")
        return False
    
    return True

def start_server():
    """Start the FastAPI server"""
    try:
        # Add src directory to Python path
        src_path = Path(__file__).parent / "src"
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))
        
        # Change to src directory
        os.chdir(src_path)
        
        # Import and start the app
        from routes.app import app
        import uvicorn
        
        print("🚀 Starting RAG Evaluator UI Server...")
        print("=" * 60)
        print("📊 Main Interface:     http://localhost:8001")
        print("📖 API Documentation:  http://localhost:8001/api/docs")
        print("🔄 Interactive API:    http://localhost:8001/api/redoc")
        print("💡 Health Check:       http://localhost:8001/api/health")
        print("=" * 60)
        print("🎯 Features:")
        print("   • Drag & drop file upload")
        print("   • Real-time progress tracking")
        print("   • Performance optimization presets")
        print("   • Beautiful result visualization")
        print("   • Async batch processing (3-5x faster)")
        print("=" * 60)
        print("⏹️  Press Ctrl+C to stop the server")
        print("")
        
        # Open browser after a short delay
        def open_browser():
            time.sleep(2)
            try:
                webbrowser.open("http://localhost:8001")
                print("🌐 Opened browser automatically")
            except Exception as e:
                print(f"💻 Could not open browser automatically: {e}")
                print("💻 Please open http://localhost:8001 in your browser manually")
        
        import threading
        browser_thread = threading.Thread(target=open_browser)
        browser_thread.daemon = True
        browser_thread.start()
        
        # Start the server
        uvicorn.run(
            app, 
            host="0.0.0.0", 
            port=8001, 
            reload=False,  # Disable reload in production
            access_log=True
        )
        
    except KeyboardInterrupt:
        print("\n")
        print("🛑 Server stopped by user")
        print("👋 Thank you for using RAG Evaluator!")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're in the RAG_Evaluator directory")
        print("💡 Try: cd RAG_Evaluator && python start_ui.py")
        print("💡 Install missing dependencies: pip install -r src/requirements.txt")
    except PermissionError as e:
        print(f"❌ Permission error: {e}")
        print("💡 Try running with appropriate permissions")
        print("💡 Check if port 8001 is available or in use by another application")
    except OSError as e:
        if "Address already in use" in str(e):
            print("❌ Port 8001 is already in use")
            print("💡 Stop any other instances of the application")
            print("💡 Or wait a few moments and try again")
        else:
            print(f"❌ Network error: {e}")
            print("💡 Check your network configuration")
    except Exception as e:
        print(f"❌ Unexpected error starting server: {e}")
        print("💡 Check the error message above and try again")
        print("💡 For support, see README.md or create an issue on GitHub")

def show_help():
    """Show help information"""
    print(__doc__)
    print("\n🔧 Troubleshooting:")
    print("   • Make sure you're in the RAG_Evaluator directory")
    print("   • Install dependencies: pip install -r src/requirements.txt")
    print("   • Check Python version: Python 3.8+ required")
    print("   • Ensure you have sufficient disk space (>1GB recommended)")
    print("   • Check internet connectivity for API calls")
    print("   • For issues, check the console output for error details")
    print("\n📋 Command Line Options:")
    print("   • python start_ui.py           - Start the server")
    print("   • python start_ui.py --help    - Show this help")
    print("   • python start_ui.py --version - Show version information")
    print("\n🌐 Accessing the Application:")
    print("   • Web Interface: http://localhost:8001")
    print("   • API Docs: http://localhost:8001/api/docs")
    print("   • Health Check: http://localhost:8001/api/health")
    print("\n📚 For detailed documentation, see README.md and UI_README.md")

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"💡 Current Python version: {sys.version}")
        print("💡 Please upgrade Python and try again")
        return False
    return True

def main():
    """Main entry point"""
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            show_help()
            return
        elif sys.argv[1] in ['-v', '--version', 'version']:
            print("🧠 RAG Evaluator UI v2.0.0 - Async Batch Processing Edition")
            print("📅 Built: 2024")
            print(f"🐍 Python: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (3.8+ required)")
            print("🌐 FastAPI + Modern Web UI")
            print("📊 RAGAS + CRAG + LLM Evaluation")
            print("⚡ 3-5x faster async processing")
            return
    
    print("🧠 RAG Evaluator - Advanced Performance Testing Suite")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Check if we're in the right directory
    if not Path("src/routes/app.py").exists():
        print("❌ Error: Not in RAG_Evaluator directory")
        print("💡 Please run this script from the RAG_Evaluator root directory")
        print("💡 Example: cd RAG_Evaluator && python start_ui.py")
        return
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    if not check_dependencies():
        return
    
    print("✅ All dependencies found")
    
    # Check for optional dependencies
    optional_packages = ['pymongo']
    missing_optional = []
    
    for package in optional_packages:
        try:
            __import__(package)
        except ImportError:
            missing_optional.append(package)
    
    if missing_optional:
        print("ℹ️  Optional features available with additional packages:")
        if 'pymongo' in missing_optional:
            print("   • MongoDB result storage: pip install pymongo")
    
    # System info
    print(f"🐍 Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🔧 Platform: {sys.platform}")
    
    print("")
    
    # Start the server
    start_server()

if __name__ == "__main__":
    main() 