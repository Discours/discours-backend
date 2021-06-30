import uvicorn
from settings import PORT

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
