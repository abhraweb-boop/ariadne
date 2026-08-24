"""Autonomy policy tier tests (no model)."""

from __future__ import annotations

import pytest

import ariadne_runtime.policy as policy


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(policy, "_configured_tier", lambda: "governed")


def test_governed_defaults():
    t = policy.active()
    assert t["name"] == "governed"
    assert t["max_attempts"] == 2
    assert t["cell_timeout_s"] == 300.0
    assert t["max_iterations"] == 10_000
    assert t["auto_steer"] is False


def test_unleashed_knobs(monkeypatch):
    monkeypatch.setattr(policy, "_configured_tier", lambda: "unleashed")
    t = policy.active()
    assert t["max_attempts"] == 5
    assert t["cell_timeout_s"] == 3600.0
    assert t["max_iterations"] == 200_000
    assert t["auto_steer"] is True


def test_unknown_tier_falls_back():
    t = policy.get("yolo-mode")
    assert t["name"] == "governed"


def test_explicit_overrides_config():
    assert policy.get("unleashed")["auto_steer"] is True
    assert policy.active()["name"] == "governed"  # config still governed


def test_floors_constant():
    assert "credentials-entry" in policy.NEVER
    assert "payment-ui" in policy.NEVER
    assert "destructive-os-ops" in policy.NEVER
