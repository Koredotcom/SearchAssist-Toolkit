import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from services.run_eval import runeval
from services.mailService import mailService

app = FastAPI()

class Params(BaseModel):
    sheet_name: str = None
    evaluate_ragas: bool = False
    evaluate_crag: bool = False
    use_search_api: bool = False
    llm_model: str = None
    save_db: bool = False

class Body(BaseModel):
    excel_file: str
    config_file: str
    params: Params




@app.post('/runeval')
async def run_eval(body: Body):

    if body is None:
        return JSONResponse(content={"error": "Request body is required"}, status_code=400)
    
    if body.excel_file is None or body.config_file is None:
        return JSONResponse(content={"error": "Excel and config files are required"}, status_code=400)
    
    if body.params is None:
        return JSONResponse(content={"error": "Params are required"}, status_code=400)
    
    param_config = {
        "sheet_name": body.params.sheet_name,
        "evaluate_ragas": body.params.evaluate_ragas,
        "evaluate_crag": body.params.evaluate_crag,
        "use_search_api": body.params.use_search_api,
        "llm_model": body.params.llm_model,
        "save_db": body.params.save_db
    }
    

    excel_file = body.excel_file
    config_file = body.config_file
    
    try:
        response = await runeval(excel_file, config_file, param_config)
        return JSONResponse(content={"status": "Success", "message": f"Evaluation is successfully completed. {response}"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    
@app.post('/mailService')
async def mail_service(send_mail: bool = False):
    try:
        mailService(sendMail = send_mail)
        return JSONResponse(content={"status": "Success", "message": "Mail content generated successfully"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
    

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)