import sys
import uvicorn
from settings import PORT

if __name__ == "__main__":
    x = ""
    if len(sys.argv) > 1:
        x = sys.argv[1]
    if x == "dev":
        print("DEV MODE")
        headers = [
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD"),
            ("Access-Control-Allow-Origin", "http://localhost:3000"),
            (
                "Access-Control-Allow-Headers",
                "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Auth",
            ),
            ("Access-Control-Expose-Headers", "Content-Length,Content-Range"),
            ("Access-Control-Allow-Credentials", "true"),
        ]
        uvicorn.run(
            "main:app", host="localhost", port=8080, headers=headers
        )  # , ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
    elif x == "migrate":
        from migration import migrate

        migrate()
    else:
        uvicorn.run("main:app", host="0.0.0.0", port=PORT)
