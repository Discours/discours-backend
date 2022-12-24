import sys
import os
import uvicorn

from settings import PORT, DEV_SERVER_STATUS_FILE_NAME


def exception_handler(exception_type, exception, traceback, debug_hook=sys.excepthook):
    print("%s: %s" % (exception_type.__name__, exception))


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

local_headers = [
    ("Access-Control-Allow-Methods", "GET, POST, OPTIONS, HEAD"),
    ("Access-Control-Allow-Origin", "http://localhost:3000"),
    (
        "Access-Control-Allow-Headers",
        "DNT,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Range,Authorization",
    ),
    ("Access-Control-Expose-Headers", "Content-Length,Content-Range"),
    ("Access-Control-Allow-Credentials", "true"),
]

if __name__ == "__main__":
    x = ""
    if len(sys.argv) > 1:
        x = sys.argv[1]
    if x == "dev":
        if os.path.exists(DEV_SERVER_STATUS_FILE_NAME):
            os.remove(DEV_SERVER_STATUS_FILE_NAME)
        want_reload = False
        if "reload" in sys.argv:
            print("MODE: DEV + RELOAD")
            want_reload = True
        else:
            print("MODE: DEV")

        uvicorn.run(
            "main:dev_app",
            host="localhost",
            port=8080,
            headers=local_headers,
            # log_config=log_settings,
            log_level=None,
            access_log=True,
            reload=want_reload
        )  # , ssl_keyfile="discours.key", ssl_certfile="discours.crt")
    elif x == "migrate":
        from migration import migrate
        print("MODE: MIGRATE")

        migrate()
    elif x == "bson":
        from migration.bson2json import json_tables
        print("MODE: BSON")

        json_tables()
    else:
        sys.excepthook = exception_handler
        uvicorn.run(
            "main:app",
            host="0.0.0.0",
            port=PORT,
            proxy_headers=True,
            server_header=True
        )
