"""OpenTelemetry tracing, metrics and logging for FastAPI."""

import logging
import os
import time

from fastapi import FastAPI, Request
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    ConsoleLogRecordExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

logger = logging.getLogger("git_rest_lab2.telemetry")


def configure_telemetry(app: FastAPI) -> None:
    """Configure telemetry when explicitly enabled."""
    if os.getenv("OTEL_ENABLED", "false").lower() != "true":
        return

    service_name = os.getenv(
        "OTEL_SERVICE_NAME", "lab8-fastapi"
    )
    mode = os.getenv("OTEL_EXPORT_MODE", "console").lower()
    endpoint = os.getenv(
        "OTEL_EXPORTER_OTLP_ENDPOINT",
        "http://otel-collector:4317",
    )

    if mode not in {"console", "otlp"}:
        raise ValueError("OTEL_EXPORT_MODE must be console or otlp")

    resource = Resource.create({
        "service.name": service_name,
        "service.version": app.version,
        "deployment.environment.name": "lab8-local",
    })

    if mode == "otlp":
        span_exporter = OTLPSpanExporter(
            endpoint=endpoint,
            insecure=True,
        )
        metric_exporter = OTLPMetricExporter(
            endpoint=endpoint,
            insecure=True,
        )
        log_exporter = OTLPLogExporter(
            endpoint=endpoint,
            insecure=True,
        )
    else:
        span_exporter = ConsoleSpanExporter()
        metric_exporter = ConsoleMetricExporter()
        log_exporter = ConsoleLogRecordExporter()

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(span_exporter)
    )
    trace.set_tracer_provider(tracer_provider)

    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=10000,
    )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader],
    )
    metrics.set_meter_provider(meter_provider)

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(log_exporter)
    )
    set_logger_provider(logger_provider)

    app_logger = logging.getLogger("git_rest_lab2")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(
        LoggingHandler(
            level=logging.INFO,
            logger_provider=logger_provider,
        )
    )

    request_counter = metrics.get_meter(
        service_name
    ).create_counter(
        "http.server.requests.lab8",
        unit="1",
        description="Number of HTTP requests",
    )

    request_duration = metrics.get_meter(
        service_name
    ).create_histogram(
        "http.server.duration.lab8",
        unit="ms",
        description="HTTP request duration in milliseconds",
    )

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            logger.exception("Unhandled HTTP request error")
            raise
        finally:
            duration_ms = (
                time.perf_counter() - start
            ) * 1000

            route = request.scope.get("route")
            route_name = (
                getattr(route, "path", None)
                or "unmatched"
            )

            attributes = {
                "http.request.method": request.method,
                "http.route": route_name,
                "http.response.status_code": status_code,
            }

            request_counter.add(1, attributes)
            request_duration.record(
                duration_ms, attributes
            )

            logger.info(
                "HTTP %s %s status=%s duration_ms=%.2f",
                request.method,
                route_name,
                status_code,
                duration_ms,
            )

    FastAPIInstrumentor.instrument_app(app)
    PsycopgInstrumentor().instrument()

    logger.info(
        "OpenTelemetry configured: service=%s mode=%s",
        service_name,
        mode,
    )
    