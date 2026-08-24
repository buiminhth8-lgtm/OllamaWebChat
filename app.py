#!/usr/bin/env python3
import os
from pathlib import Path
from typing import Optional, Union

from flask import Flask

from demo import demo_bp
from ollama_service import OllamaServiceManager
from platform_scan import platform_bp
from routes import bp
from runtime_settings import DEFAULT_SETTINGS_PATH, RuntimeSettingsStore


def create_app(settings_path: Optional[Union[str, Path]] = None) -> Flask:
    app = Flask(__name__)
    settings_store = RuntimeSettingsStore(settings_path or DEFAULT_SETTINGS_PATH)
    app.extensions["runtime_settings"] = settings_store
    app.extensions["ollama_service"] = OllamaServiceManager(settings_store)
    app.register_blueprint(bp)
    app.register_blueprint(platform_bp)
    app.register_blueprint(demo_bp)
    return app


app = create_app()


if __name__ == "__main__":
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "3000"))
    app.run(host=host, port=port, threaded=True)
