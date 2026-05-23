import re
from pathlib import Path

from conftest import PACKAGE_DIR

from robot_mima_mkv30 import model_utils

RESERVED_LAUNCH_ARGS = {'use_sim_mode', 'namespace', 'robot_name'}


def _normalize_package_reference(value: str) -> str:
    return value.replace('$(find robot_mima_mkv30)/', 'package://robot_mima_mkv30/')


def _xacro_arg_defaults(xacro_file: Path) -> dict[str, str]:
    pattern = re.compile(r'<xacro:arg\s+name="([^"]+)"\s+default="([^"]*)"')
    return dict(pattern.findall(xacro_file.read_text(encoding='utf-8')))


def _xacro_arg_names(xacro_file: Path) -> set[str]:
    pattern = re.compile(r'<xacro:arg\s+name="([^"]+)"')
    return set(pattern.findall(xacro_file.read_text(encoding='utf-8')))


def test_base_xargs_defaults_match_common_xacro_defaults() -> None:
    xacro_defaults = _xacro_arg_defaults(PACKAGE_DIR / 'urdf' / 'includes' / 'common.xacro')
    xacro_defaults = {k: v for k, v in xacro_defaults.items() if k not in RESERVED_LAUNCH_ARGS}

    xargs = model_utils._get_xargs('base')

    for xarg_name in xacro_defaults:
        assert xargs[xarg_name]['default_value'] == _normalize_package_reference(xacro_defaults[xarg_name])


def test_base_xargs_match_common_xacro_args() -> None:
    common_arg_names = _xacro_arg_names(PACKAGE_DIR / 'urdf' / 'includes' / 'common.xacro') - RESERVED_LAUNCH_ARGS

    assert set(model_utils.get_xarg_names('base')) == common_arg_names


def test_model_utils_lists_base_model() -> None:
    assert model_utils.get_models() == ['base', 'sensors1']
    assert model_utils.get_models_with_xargs() == ['base', 'sensors1']
    assert model_utils.model_exists('base')
    assert model_utils.model_exists('sensors1')
    assert model_utils.model_has_xargs('base')
    assert model_utils.model_has_xargs('sensors1')
    assert not model_utils.model_exists('forklift')
