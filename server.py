import uvicorn
from settings import PORT

import sys

if __name__ == '__main__':
	dev_mode = len(sys.argv) > 1 and sys.argv[1] == "dev"
	if dev_mode :
		uvicorn.run("main:app", host="0.0.0.0", port=8080, ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
	else :
		uvicorn.run("main:app", host="0.0.0.0", port=PORT)
