"""OpenTelemetry tracing setup. Safe to call when no collector is configured."""
from __future__ import annotations

import structlog

from app.config.settings import ObservabilitySettings

logger = structlog.get_logger(__name__)


def configure_tracing(settings: ObservabilitySettings, app: object, engine: object) -> None:
    if not settings.traces_enabled:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("otel.instrumentation_unavailable")
        return

    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)

    if settings.otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otlp_endpoint))
        )

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)  # type: ignore[arg-type]
    SQLAlchemyInstrumentor().instrument(engine=getattr(engine, "sync_engine", engine))
    logger.info("otel.configured", endpoint=settings.otlp_endpoint or "none")
