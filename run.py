# run.py
import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=3213,
        reload=True if settings.APP_VERSION.endswith("dev") else False
    )