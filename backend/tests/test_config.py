"""Tests for config module — profile loading and settings."""

import os
import tempfile
import yaml
import pytest

from app.config import Settings, load_profile, list_profiles, save_profile
from app.models import SimulationProfile


class TestSettings:
    """Tests for the Settings configuration class."""

    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()
        assert settings.simulator_host == "0.0.0.0"
        assert settings.simulator_port == 8000
        assert settings.iberdrola_gateway_token == ""
        assert settings.log_level == "info"


class TestProfileLoading:
    """Tests for YAML profile loading and validation."""

    def test_load_valid_profile(self, tmp_path):
        """Test loading a valid YAML profile."""
        profile_data = {
            "name": "test-profile",
            "transport": {"mode": "mosquitto_via_nginx"},
            "devices": {"count": 10},
            "telemetry": {"interval_seconds": 30},
            "schedule": {"mode": "duration", "duration_minutes": 60},
        }
        profile_file = tmp_path / "test.yaml"
        with open(profile_file, "w") as f:
            yaml.dump(profile_data, f)

        profile = load_profile(profile_file)
        assert profile.name == "test-profile"
        assert profile.transport.mode.value == "mosquitto_via_nginx"
        assert profile.devices.count == 10

    def test_load_nonexistent_profile(self):
        """Test that loading a non-existent profile raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_profile("/nonexistent/path/to/profile.yaml")

    def test_load_invalid_yaml(self, tmp_path):
        """Test that loading invalid YAML raises an error."""
        profile_file = tmp_path / "invalid.yaml"
        with open(profile_file, "w") as f:
            f.write("{{invalid yaml")

        with pytest.raises(Exception):
            load_profile(profile_file)

    def test_save_and_load_profile(self, tmp_path):
        """Test saving and loading a profile round-trip."""
        profile_data = {
            "name": "round-trip-test",
            "transport": {"mode": "tb_direct"},
            "devices": {"count": 25},
            "telemetry": {"interval_seconds": 15},
            "schedule": {"mode": "infinite"},
        }

        # Override profiles dir
        import app.config as config_module

        original_dir = config_module.PROFILES_DIR
        config_module.PROFILES_DIR = tmp_path

        try:
            profile = save_profile("round-trip-test", profile_data)
            assert profile.name == "round-trip-test"
            assert profile.transport.mode.value == "tb_direct"
            assert profile.devices.count == 25

            # Verify the file exists
            saved_file = tmp_path / "round-trip-test.yaml"
            assert saved_file.exists()

            # Load it back
            loaded = load_profile(saved_file)
            assert loaded.name == "round-trip-test"
        finally:
            config_module.PROFILES_DIR = original_dir
