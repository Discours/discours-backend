import uvicorn
from settings import PORT

if __name__ == '__main__':
<<<<<<< HEAD
    uvicorn.run("main:app", host="0.0.0.0", port=8081, ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
=======
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
>>>>>>> remotes/origin/dev
