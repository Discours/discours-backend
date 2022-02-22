import uvicorn
from settings import PORT, INBOX_SERVICE_PORT

import sys

if __name__ == '__main__':
	dev_mode = len(sys.argv) > 1 and sys.argv[1] == "dev"
	inbox_service = len(sys.argv) > 1 and sys.argv[1] == "inbox"
	if dev_mode:
		print("DEV MODE")
		uvicorn.run("main:app", host="0.0.0.0", port=8080, ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
	elif inbox_service:
		print("INBOX SERVICE")
		uvicorn.run("inbox_main:app", host="0.0.0.0", port=INBOX_SERVICE_PORT)
	else :
		uvicorn.run("main:app", host="0.0.0.0", port=PORT)
