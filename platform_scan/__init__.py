from flask import Blueprint, Response, jsonify, render_template

from platform_scan.scanner import PlatformScanner


platform_bp = Blueprint("platform", __name__)
scanner = PlatformScanner()


@platform_bp.get("/platform")
def platform_page():
    return render_template("platform.html")


@platform_bp.post("/api/platform/scan")
def platform_scan():
    return Response(
        scanner.stream(),
        content_type="application/x-ndjson; charset=utf-8",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@platform_bp.get("/api/platform/latest")
def platform_latest():
    return jsonify(scanner.latest())


@platform_bp.get("/api/platform/health")
def platform_health():
    return jsonify({"ok": True, "module": "platform_scan", "collectors": len(scanner.collectors)})
