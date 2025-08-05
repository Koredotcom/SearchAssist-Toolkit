import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from werkzeug.utils import secure_filename
import pandas as pd
import shutil
from main import run

async def process_files(excel_file, config_file, session_id=None):
    """
    Process files with session-specific isolation to prevent multi-user conflicts.
    Each user gets their own config and Excel file copies.
    """
    
    # Use session-specific directories if session_id provided
    if session_id:
        # Session-based file handling for multi-user safety
        from utils.sessionManager import get_session_manager
        session_manager = get_session_manager()
        session_dir = session_manager.get_session_directory(session_id)
        
        # Create session-specific config directory
        session_config_dir = os.path.join(session_dir, "config")
        os.makedirs(session_config_dir, exist_ok=True)
        
        excel_file_name = excel_file.split("/")[-1]
        excel_filename = secure_filename(excel_file_name)
        
        # Session-specific paths (NO SHARED FILES!)
        # Use input_ prefix pattern to match the expected filename format
        excel_path = os.path.join(session_dir, f"input_{session_id}_{excel_filename}")
        config_path = os.path.join(session_config_dir, f"config_{session_id}.json")
        
        print(f"🔐 Using session-specific paths for session {session_id[:8]}...")
        print(f"📄 Excel: {excel_path}")
        print(f"⚙️ Config: {config_path}")
        
    else:
        # Fallback to legacy behavior (for backwards compatibility)
        print("⚠️ WARNING: No session ID provided - using legacy shared file approach!")
        INPUT_UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "../")
        CONFIG_UPLOAD_FOLDER = os.path.join(INPUT_UPLOAD_FOLDER, "config")
        
        # Ensure config directory exists
        os.makedirs(CONFIG_UPLOAD_FOLDER, exist_ok=True)
        
        excel_file_name = excel_file.split("/")[-1]
        excel_filename = secure_filename(excel_file_name)
        
        excel_path = os.path.join(INPUT_UPLOAD_FOLDER, excel_filename)
        config_path = os.path.join(CONFIG_UPLOAD_FOLDER, 'config.json')
    
    # Copy user-specific config (ISOLATED per session)
    with open(config_file, 'r') as f:
        config_content = f.read()
        with open(config_path, 'w') as f2:
            f2.write(config_content)
            
    # Debug: Check source file before copying
    print(f"🔍 Source Excel file: {excel_file}")
    print(f"🔍 Source file exists: {os.path.exists(excel_file)}")
    if os.path.exists(excel_file):
        print(f"🔍 Source file size: {os.path.getsize(excel_file)} bytes")
    
    # Copy Excel file to session-specific location
    try:
        shutil.copy2(excel_file, excel_path)
        print(f"✅ Copied Excel file from {excel_file} to {excel_path}")
        
        # Verify the copy was successful
        if os.path.exists(excel_path):
            print(f"✅ Destination file exists: {excel_path}")
            print(f"✅ Destination file size: {os.path.getsize(excel_path)} bytes")
        else:
            print(f"❌ Destination file NOT found after copy: {excel_path}")
            
    except Exception as copy_error:
        print(f"❌ Error copying Excel file: {copy_error}")
        raise Exception(f"Failed to copy Excel file: {copy_error}")
    
    return excel_path, config_path  # Return both paths for session isolation


async def runeval(excel_file, config_file, params, session_id=None):
    
    excel_path, session_config_path = await process_files(excel_file, config_file, session_id)
    
    # Extract sheet_name from params
    sheet_name = params.get("sheet_name", "")
    print(f"🔍 Sheet selection from UI: '{sheet_name}' (empty = all sheets)")
    print(f"🔧 Using session-specific config: {session_config_path}")
    
    try:
        return await run(excel_path, 
                        sheet_name=sheet_name,  # Pass the sheet_name parameter
                        evaluate_ragas=params.get("evaluate_ragas"), 
                        evaluate_crag=params.get("evaluate_crag"), 
                        evaluate_llm=params.get("evaluate_llm"), 
                        use_search_api=params.get("use_search_api"), 
                        llm_model=params.get("llm_model"), 
                        save_db=params.get("save_db"),
                        batch_size=params.get("batch_size", 10),
                        max_concurrent=params.get("max_concurrent", 5),
                        session_id=session_id,
                        session_config_path=session_config_path)  # Pass session-specific config
    except Exception as e:
        raise Exception("Error in running evaluation: " + str(e))
    
    
    
