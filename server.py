import uvicorn

if __name__ == '__main__':
    uvicorn.run("main:app", host="0.0.0.0", port=8081, ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
