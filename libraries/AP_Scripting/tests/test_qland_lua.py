# AP_FLAKE8_CLEAN

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("layout", ["legacy", "sysid32"])
def test_lua_controller(layout):
    lua = shutil.which("lua5.4") or shutil.which("lua")
    if lua is None:
        pytest.skip("Install lua5.4 to run the flight-controller script tests")
    scripting = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            lua,
            str(scripting / "tests/qland_yaw_alignment_test.lua"),
            str(scripting / "applets/qland_yaw_alignment.lua"),
            layout,
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
