
import logging
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from git_rest_lab2 import telemetry


@pytest.fixture
def otel_mocks(monkeypatch):
    """Replace exporters and SDK providers with test doubles."""
    names = [
        "Resource",
        "OTLPSpanExporter",
        "OTLPMetricExporter",
        "OTLPLogExporter",
        "ConsoleSpanExporter",
        "ConsoleMetricExporter",
        "ConsoleLogRecordExporter",
        "TracerProvider",
        "BatchSpanProcessor",
        "PeriodicExportingMetricReader",
        "MeterProvider",
        "LoggerProvider",
        "BatchLogRecordProcessor",
        "FastAPIInstrumentor",
        "PsycopgInstrumentor",
    ]

    mocks = {}

    for name in names:
        mock = MagicMock(name=name)
        monkeypatch.setattr(telemetry, name, mock)
        mocks[name] = mock

    mocks["LoggingHandler"] = MagicMock(
        return_value=logging.NullHandler()
    )
    monkeypatch.setattr(
        telemetry, "LoggingHandler", mocks["LoggingHandler"]
    )

    monkeypatch.setattr(
        telemetry.trace, "set_tracer_provider", MagicMock()
    )
    monkeypatch.setattr(
        telemetry.metrics, "set_meter_provider", MagicMock()
    )
    monkeypatch.setattr(
        telemetry, "set_logger_provider", MagicMock()
    )

    meter = MagicMock()
    monkeypatch.setattr(
        telemetry.metrics, "get_meter", MagicMock(return_value=meter)
    )
    mocks["meter"] = meter

    return mocks


def test_telemetry_disabled_by_default(monkeypatch, otel_mocks):
    monkeypatch.delenv("OTEL_ENABLED", raising=False)

    app = FastAPI()
    telemetry.configure_telemetry(app)

    otel_mocks["TracerProvider"].assert_not_called()
    otel_mocks["MeterProvider"].assert_not_called()


def test_telemetry_disabled_explicitly(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "false")

    telemetry.configure_telemetry(FastAPI())

    otel_mocks["TracerProvider"].assert_not_called()


def test_invalid_export_mode(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", "invalid")

    with pytest.raises(
        ValueError, match="OTEL_EXPORT_MODE must be console or otlp"
    ):
        telemetry.configure_telemetry(FastAPI())

    otel_mocks["TracerProvider"].assert_not_called()


@pytest.mark.parametrize("mode", ["console", "otlp"])
def test_telemetry_exporters(monkeypatch, otel_mocks, mode):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", mode)
    monkeypatch.setenv("OTEL_SERVICE_NAME", "test-fastapi")
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4317"
    )

    app = FastAPI(version="0.2.0")
    telemetry.configure_telemetry(app)

    otel_mocks["Resource"].create.assert_called_once_with(
        {
            "service.name": "test-fastapi",
            "service.version": "0.2.0",
            "deployment.environment.name": "lab8-local",
        }
    )

    if mode == "console":
        for name in (
            "ConsoleSpanExporter",
            "ConsoleMetricExporter",
            "ConsoleLogRecordExporter",
        ):
            otel_mocks[name].assert_called_once()
    else:
        for name in (
            "OTLPSpanExporter",
            "OTLPMetricExporter",
            "OTLPLogExporter",
        ):
            otel_mocks[name].assert_called_once_with(
                endpoint="http://collector:4317",
                insecure=True,
            )

    otel_mocks["TracerProvider"].assert_called_once()
    otel_mocks["MeterProvider"].assert_called_once()
    otel_mocks["LoggerProvider"].assert_called_once()
    otel_mocks["BatchSpanProcessor"].assert_called_once()
    otel_mocks["BatchLogRecordProcessor"].assert_called_once()
    otel_mocks["PeriodicExportingMetricReader"].assert_called_once_with(
        otel_mocks[
            "ConsoleMetricExporter"
            if mode == "console"
            else "OTLPMetricExporter"
        ].return_value,
        export_interval_millis=10000,
    )

    otel_mocks["FastAPIInstrumentor"].instrument_app.assert_called_once_with(
        app
    )
    otel_mocks["PsycopgInstrumentor"].return_value.instrument.assert_called_once()

    otel_mocks["meter"].create_counter.assert_called_once_with(
        "http.server.requests.lab8",
        unit="1",
        description="Number of HTTP requests",
    )
    otel_mocks["meter"].create_histogram.assert_called_once_with(
        "http.server.duration.lab8",
        unit="ms",
        description="HTTP request duration in milliseconds",
    )


def test_default_console_configuration(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "TRUE")
    monkeypatch.delenv("OTEL_EXPORT_MODE", raising=False)
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)

    telemetry.configure_telemetry(FastAPI(version="1.0"))

    otel_mocks["Resource"].create.assert_called_once_with(
        {
            "service.name": "lab8-fastapi",
            "service.version": "1.0",
            "deployment.environment.name": "lab8-local",
        }
    )
    otel_mocks["ConsoleSpanExporter"].assert_called_once()


def test_default_otlp_endpoint(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", "otlp")
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    telemetry.configure_telemetry(FastAPI())

    otel_mocks["OTLPSpanExporter"].assert_called_once_with(
        endpoint="http://otel-collector:4317",
        insecure=True,
    )


def test_successful_request_records_metrics(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", "console")

    app = FastAPI()

    @app.get("/example")
    def example():
        return {"result": "ok"}

    telemetry.configure_telemetry(app)

    with TestClient(app) as client:
        response = client.get("/example")

    assert response.status_code == 200
    assert response.json() == {"result": "ok"}

    counter = otel_mocks["meter"].create_counter.return_value
    histogram = otel_mocks["meter"].create_histogram.return_value

    attributes = {
        "http.request.method": "GET",
        "http.route": "/example",
        "http.response.status_code": 200,
    }

    counter.add.assert_called_once_with(1, attributes)

    histogram.record.assert_called_once()
    duration, recorded_attributes = histogram.record.call_args.args

    assert duration >= 0
    assert recorded_attributes == attributes


def test_unmatched_route_records_404(monkeypatch, otel_mocks):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", "console")

    app = FastAPI()
    telemetry.configure_telemetry(app)

    with TestClient(app) as client:
        response = client.get("/missing")

    assert response.status_code == 404

    counter = otel_mocks["meter"].create_counter.return_value
    attributes = counter.add.call_args.args[1]

    assert attributes["http.request.method"] == "GET"
    assert attributes["http.route"] == "unmatched"
    assert attributes["http.response.status_code"] == 404


def test_unhandled_error_records_500(
    monkeypatch, otel_mocks, caplog
):
    monkeypatch.setenv("OTEL_ENABLED", "true")
    monkeypatch.setenv("OTEL_EXPORT_MODE", "console")

    app = FastAPI()

    @app.get("/broken")
    def broken():
        raise RuntimeError("Test failure")

    telemetry.configure_telemetry(app)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/broken")

    assert response.status_code == 500

    counter = otel_mocks["meter"].create_counter.return_value
    histogram = otel_mocks["meter"].create_histogram.return_value

    attributes = counter.add.call_args.args[1]

    assert attributes["http.request.method"] == "GET"
    assert attributes["http.response.status_code"] == 500

    counter.add.assert_called_once()
    histogram.record.assert_called_once()
    assert "Unhandled HTTP request error" in caplog.text
