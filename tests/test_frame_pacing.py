"""Test-suite configuration must reach mock clients and reject invalid delays."""
import subprocess
import sys

import pytest
from harness.env import ROOT
from harness.pacing import FramePacing


@pytest.mark.parametrize('pacing,expected', [
    (FramePacing(), dict(tx_message_wait=0, tx_jitter=0)),
    (FramePacing(enabled=True), dict(tx_message_wait=0.25, tx_jitter=0.1)),
    (FramePacing(enabled=True, delay=0.02, jitter=0.005), dict(tx_message_wait=0.02, tx_jitter=0.005)),
    (FramePacing(enabled=False, delay=2, jitter=1), dict(tx_message_wait=0, tx_jitter=0)),
    (FramePacing(enabled=True, delay=0, jitter=0), dict(tx_message_wait=0, tx_jitter=0)),
])
def test_client_options(pacing, expected):
    assert pacing.client_options() == expected


def collect(*args):
    return subprocess.run([sys.executable, '-m', 'pytest', '--collect-only',
                           'tests/test_catalogue_coverage.py', *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize('args,header', [
    ([], 'off (delay=0s, jitter=0s)'),
    (['--frame-pacing=on'], 'on (delay=0.25s, jitter=0..0.1s)'),
    (['-o', 'givtcp_frame_pacing=true', '-o', 'givtcp_frame_delay=0.03',
      '-o', 'givtcp_frame_jitter=0.004'], 'on (delay=0.03s, jitter=0..0.004s)'),
    (['-o', 'givtcp_frame_pacing=true', '--frame-pacing=off'], 'off (delay=0s, jitter=0s)'),
    (['-o', 'givtcp_frame_delay=1', '--frame-pacing=on', '--frame-delay=0.02',
      '--frame-jitter=0'], 'on (delay=0.02s, jitter=0..0s)'),
])
def test_pytest_configuration_and_cli_overrides(args, header):
    result = collect(*args)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'Mock Modbus frame pacing: ' + header in result.stdout


@pytest.mark.parametrize('args,field', [
    (['--frame-delay=-1'], 'delay'),
    (['--frame-delay=nan'], 'delay'),
    (['--frame-delay=inf'], 'delay'),
    (['--frame-jitter=-1'], 'jitter'),
    (['--frame-jitter=nan'], 'jitter'),
    (['--frame-jitter=inf'], 'jitter'),
    (['-o', 'givtcp_frame_delay=not-a-number'], 'delay'),
    (['-o', 'givtcp_frame_jitter=-0.1'], 'jitter'),
])
def test_invalid_values_fail_before_tests_run(args, field):
    result = collect(*args)
    assert result.returncode == pytest.ExitCode.USAGE_ERROR
    assert f'frame {field} must be finite, non-negative seconds' in result.stderr


def test_selected_pacing_reaches_real_mock_client(plants, frame_pacing):
    session = plants.get('hybrid_gen2')
    assert session.pacing == frame_pacing
    assert session.client.tx_message_wait == frame_pacing.client_options()['tx_message_wait']
    assert session.client.tx_jitter == frame_pacing.client_options()['tx_jitter']
