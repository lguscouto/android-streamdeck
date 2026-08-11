from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from scripts.phase7_android_e2e import (
    EXPECTED_TEST_CLASSES,
    _assert_instrumentation_executed,
)

REQUIRED_TEST_CLASSES = (
    "br.com.gustavo.streamdeck.OnboardingFlowInstrumentedTest",
    "br.com.gustavo.streamdeck.VisualGoldenInstrumentedTest",
    "br.com.gustavo.streamdeck.network.PairingFlowInstrumentedTest",
)


def _write_suite(
    report_dir: Path,
    classes: tuple[str, ...],
    *,
    failed: bool = False,
    include_attributes: bool = True,
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    testcases = []
    for index, classname in enumerate(classes):
        failure = "<failure>failed</failure>" if failed and index == 0 else ""
        testcases.append(
            f'<testcase classname="{classname}" name="test_{index}">'
            f"{failure}</testcase>"
        )
    attributes = (
        f'tests="{len(classes)}" failures="{int(failed)}" errors="0" skipped="0"'
        if include_attributes
        else ""
    )
    report = report_dir / "TEST-aggregate.xml"
    report.write_text(
        f'<testsuite name="aggregate" {attributes}>{"".join(testcases)}</testsuite>',
        encoding="utf-8",
    )
    return report


def test_expected_class_contract_is_literal_and_complete() -> None:
    assert EXPECTED_TEST_CLASSES == REQUIRED_TEST_CLASSES


def test_instrumentation_gate_requires_all_expected_classes(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    _write_suite(report_dir, REQUIRED_TEST_CLASSES)

    _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_missing_expected_class(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    _write_suite(report_dir, REQUIRED_TEST_CLASSES[:1])

    with pytest.raises(RuntimeError, match="missing or duplicated"):
        _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_duplicate_expected_class(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    _write_suite(report_dir, REQUIRED_TEST_CLASSES + (REQUIRED_TEST_CLASSES[0],))

    with pytest.raises(RuntimeError, match="missing or duplicated"):
        _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_failed_expected_class(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    _write_suite(report_dir, REQUIRED_TEST_CLASSES, failed=True)

    with pytest.raises(RuntimeError, match="without failures or skips"):
        _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_missing_xml_attributes(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    _write_suite(report_dir, REQUIRED_TEST_CLASSES, include_attributes=False)

    with pytest.raises(RuntimeError, match="misses attributes"):
        _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_invalid_xml(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "TEST-invalid.xml").write_text(
        "<testsuite><testcase>",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="invalid instrumented XML"):
        _assert_instrumentation_executed(android_root, time.time() - 1)


def test_instrumentation_gate_rejects_stale_report(tmp_path: Path) -> None:
    android_root = tmp_path
    report_dir = android_root / "app" / "build" / "outputs" / "androidTest-results"
    report = _write_suite(report_dir, REQUIRED_TEST_CLASSES)
    stale = time.time() - 30
    os.utime(report, (stale, stale))

    with pytest.raises(RuntimeError, match="fresh instrumented"):
        _assert_instrumentation_executed(android_root, time.time())
