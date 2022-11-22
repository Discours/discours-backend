import sys

import uvicorn

from settings import PORT

log_settings = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'default': {
            '()': 'uvicorn.logging.DefaultFormatter',
            'fmt': '%(levelprefix)s %(message)s',
            'use_colors': None
        },
        'access': {
            '()': 'uvicorn.logging.AccessFormatter',
            'fmt': '%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
        }
    },
    'handlers': {
        'default': {
            'formatter': 'default',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stderr'
        },
        'access': {
            'formatter': 'access',
            'class': 'logging.StreamHandler',
            'stream': 'ext://sys.stdout'
        }
    },
    'loggers': {
        'uvicorn': {
            'handlers': ['default'],
            'level': 'INFO'
        },
        'uvicorn.error': {
            'level': 'INFO',
            'handlers': ['default'],
            'propagate': True
        },
        'uvicorn.access': {
            'handlers': ['access'],
            'level': 'INFO',
            'propagate': False
        }
    }
}

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
                "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization",
            ),
            ("Access-Control-Expose-Headers", "Content-Length,Content-Range"),
            ("Access-Control-Allow-Credentials", "true"),
        ]
        uvicorn.run(
            "main:app",
            host="localhost",
            port=8080,
            headers=headers,
            # log_config=LOGGING_CONFIG,
            log_level=None,
            access_log=True
        )  # , ssl_keyfile="discours.key", ssl_certfile="discours.crt", reload=True)
    elif x == "migrate":
        from migration import migrate

        migrate()
    else:
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=PORT,
            proxy_headers=True,
            server_header=True
        )
