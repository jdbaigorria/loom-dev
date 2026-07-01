"""Tests for declarative OpenTelemetry wiring (app.yml telemetry block)."""

import os

import pytest

import loom.core.telemetry as tel
from loom.schemas.config.app import AppConfig
from loom.schemas.config.telemetry import TelemetryConfig


@pytest.fixture(autouse=True)
def reset_state():
    """Reset the process-global init guard around each test."""
    tel._initialized = False
    yield
    tel._initialized = False


class TestTelemetrySchema:
    def test_app_config_accepts_telemetry_block(self):
        cfg = AppConfig(telemetry={"enabled": True, "exporter": "console", "metrics": True})
        assert cfg.telemetry is not None
        assert cfg.telemetry.enabled and cfg.telemetry.exporter == "console"

    def test_default_app_config_has_no_telemetry(self):
        assert AppConfig().telemetry is None

    def test_invalid_exporter_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TelemetryConfig(exporter="datadog")


class TestSetupTelemetry:
    def test_none_config_is_noop(self):
        assert tel.setup_telemetry(None) is False

    def test_disabled_config_is_noop(self):
        assert tel.setup_telemetry(TelemetryConfig(enabled=False)) is False

    def test_otlp_exporter_setup(self, mocker):
        fake = mocker.MagicMock()
        mocker.patch.object(tel.sx, "StrandsTelemetry", return_value=fake)
        assert tel.setup_telemetry(TelemetryConfig(enabled=True, exporter="otlp")) is True
        fake.setup_otlp_exporter.assert_called_once()
        fake.setup_console_exporter.assert_not_called()

    def test_console_exporter_setup(self, mocker):
        fake = mocker.MagicMock()
        mocker.patch.object(tel.sx, "StrandsTelemetry", return_value=fake)
        tel.setup_telemetry(TelemetryConfig(enabled=True, exporter="console"))
        fake.setup_console_exporter.assert_called_once()
        fake.setup_otlp_exporter.assert_not_called()

    def test_metrics_enabled_calls_setup_meter(self, mocker):
        fake = mocker.MagicMock()
        mocker.patch.object(tel.sx, "StrandsTelemetry", return_value=fake)
        tel.setup_telemetry(TelemetryConfig(enabled=True, exporter="otlp", metrics=True))
        fake.setup_meter.assert_called_once()

    def test_metrics_disabled_skips_setup_meter(self, mocker):
        fake = mocker.MagicMock()
        mocker.patch.object(tel.sx, "StrandsTelemetry", return_value=fake)
        tel.setup_telemetry(TelemetryConfig(enabled=True, metrics=False))
        fake.setup_meter.assert_not_called()

    def test_idempotent_setup(self, mocker):
        ctor = mocker.patch.object(tel.sx, "StrandsTelemetry")
        tel.setup_telemetry(TelemetryConfig(enabled=True))
        assert tel.setup_telemetry(TelemetryConfig(enabled=True)) is True
        ctor.assert_called_once()

    def test_missing_capability_warns_and_skips(self, mocker):
        mocker.patch.object(tel.sx, "StrandsTelemetry", None)
        assert tel.setup_telemetry(TelemetryConfig(enabled=True)) is False

    def test_service_name_sets_otel_env(self, mocker, monkeypatch):
        monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
        mocker.patch.object(tel.sx, "StrandsTelemetry", return_value=mocker.MagicMock())
        tel.setup_telemetry(TelemetryConfig(enabled=True, service_name="my-agents"))
        assert os.environ["OTEL_SERVICE_NAME"] == "my-agents"
