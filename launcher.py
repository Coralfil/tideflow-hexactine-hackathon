import os
import sys
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Ensure backend can be imported
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from app.main import create_app

def get_application() -> FastAPI:
    app = create_app()
    
    if getattr(sys, 'frozen', False):
        base_dir = sys._MEIPASS
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
    dist_dir = os.path.join(base_dir, "frontend", "dist")
    
    if os.path.isdir(dist_dir):
        assets_dir = os.path.join(dist_dir, "assets")
        if os.path.isdir(assets_dir):
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
            
        @app.get("/{catchall:path}")
        async def serve_spa(catchall: str):
            if catchall.startswith("api/"):
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail="Not Found")
            
            file_path = os.path.join(dist_dir, catchall)
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            
            return FileResponse(os.path.join(dist_dir, "index.html"))
            
    return app

app = get_application()

if __name__ == "__main__":
    uvicorn.run("launcher:app", host="127.0.0.1", port=8010, log_level="info")
