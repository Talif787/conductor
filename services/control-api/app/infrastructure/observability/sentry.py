"""Optional Sentry error tracking.

Enabled only when CONDUCTOR_OTEL_SENTRY_DSN is set. The SDK is imported lazily
so the dependency is not required unless Sentry is turned on, and initialization
failures never break app startup.
"""

from __future__ import annotations

import structlog

from app.config.settings import ObservabilitySettings

logger = structlog.get_logger(__name__)


def configure_sentry(settings: ObservabilitySettings, environment: str) -> None:
    dsn = settings.sentry_dsn
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "sentry.sdk_missing",
            detail="set CONDUCTOR_OTEL_SENTRY_DSN and install sentry-sdk",
        )
        return
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            # Errors only: performance tracing is disabled to conserve the free
            # Sentry quota (5,000 errors/month on the Developer tier).
            traces_sample_rate=0.0,
            send_default_pii=False,
        )
        logger.info("sentry.enabled", environment=environment)
    except Exception as exc:  # never let telemetry setup break the app
        logger.warning("sentry.init_failed", error=str(exc))
