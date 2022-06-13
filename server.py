import uvicorn
from settings import PORT, INBOX_SERVICE_PORT

import sys

if __name__ == '__main__':
	dev_mode = len(sys.argv) > 1 and sys.argv[1] == "dev"
	inbox_service = len(sys.argv) > 1 and sys.argv[1] == "inbox"
	if dev_mode:
		print("DEV MODE")
		headers = [
			("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD"),
			("Access-Control-Allow-Origin", "http://localhost:3000"),
			("Access-Control-Allow-Headers", "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range"),
			("Access-Control-Expose-Headers", "Content-Length,Content-Range"),
			("Access-Control-Allow-Credentials", "true")
		]
		uvicorn.run("main:app", host="localhost", port=8080, headers=headers) #, ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
	elif inbox_service:
		print("INBOX SERVICE")
		uvicorn.run("inbox_main:app", host="0.0.0.0", port=INBOX_SERVICE_PORT)
	else :
		uvicorn.run("main:app", host="0.0.0.0", port=PORT)
