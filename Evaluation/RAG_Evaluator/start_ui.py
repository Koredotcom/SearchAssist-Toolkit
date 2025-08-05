#!/usr/bin/env python3
"""
RAG Evaluator UI Startup Script
===============================

This script starts the RAG Evaluator web interface with the enhanced UI.

Usage:
    python start_ui.py

The UI will be available at:
    - Main Interface: http://localhost:8000
    - API Documentation: http://localhost:8000/api/docs
    - Interactive API: http://localhost:8000/api/redoc

Features:
    - Modern drag & drop file upload
    - Real-time progress tracking
    - Performance optimization settings
    - Beautiful result visualization
    - Downloadable reports
"""

import os
import sys
import subprocess
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
        'aiohttp'
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
        print("\n💡 Install missing packages with:")
        print(f"   pip install {' '.join(missing_packages)}")
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
            except:
                print("💻 Please open http://localhost:8001 in your browser")
        
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
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're in the RAG_Evaluator directory")
        print("💡 Try: cd RAG_Evaluator && python start_ui.py")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        print("💡 Check the error message above and try again")

def show_help():
    """Show help information"""
    print(__doc__)
    print("\n🔧 Troubleshooting:")
    print("   • Make sure you're in the RAG_Evaluator directory")
    print("   • Install dependencies: pip install -r src/requirements.txt")
    print("   • Check Python version: Python 3.8+ required")
    print("   • For issues, check the console output for error details")

def main():
    """Main entry point"""
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help', 'help']:
            show_help()
            return
        elif sys.argv[1] in ['-v', '--version', 'version']:
            print("RAG Evaluator UI v2.0.0 - Async Batch Processing Edition")
            return
    
    print("🧠 RAG Evaluator - Advanced Performance Testing Suite")
    print("=" * 60)
    
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
    print("")
    
    # Start the server
    start_server()

if __name__ == "__main__":
    main() 