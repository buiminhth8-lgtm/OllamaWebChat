#!/usr/bin/env python3
import os

from flask import Flask

from platform_scan import platform_bp
from routes import bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp)
    app.register_blueprint(platform_bp)
    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "3000"))
    app.run(host=host, port=port, threaded=True)
