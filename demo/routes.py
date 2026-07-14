from flask import Blueprint, jsonify, render_template

from demo import mock_data


demo_bp = Blueprint("demo", __name__)


@demo_bp.get("/demo")
def demo_page():
    return render_template("demo.html")


@demo_bp.get("/api/demo/config")
def demo_config():
    return jsonify(mock_data.get_config())


@demo_bp.get("/api/demo/scenario")
def demo_scenario():
    return jsonify(mock_data.get_scenario())


@demo_bp.get("/api/demo/report")
def demo_report():
    return jsonify(mock_data.get_report())


@demo_bp.get("/api/demo/metrics")
def demo_metrics():
    return jsonify(mock_data.get_metrics())
