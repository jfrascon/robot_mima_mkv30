import importlib.util
from types import ModuleType

import pytest
from conftest import PACKAGE_DIR


def test_resolve_spawner_options_accepts_exposed_flags_and_value_options() -> None:
    module = _load_ros2_control_launch_module()

    assert module._resolve_spawner_options(
        'spawner_options', '--inactive --switch-timeout 60.0 --service-call-timeout 15.0 --no-switch-asap'
    ) == ['--inactive', '--switch-timeout', '60.0', '--service-call-timeout', '15.0', '--no-switch-asap']


def test_resolve_spawner_options_rejects_controller_ros_args() -> None:
    module = _load_ros2_control_launch_module()

    with pytest.raises(ValueError, match='--controller-ros-args'):
        module._resolve_spawner_options(
            'spawner_options', '--inactive --controller-ros-args "--ros-args --param use_sim_time:=true"'
        )


def test_resolve_spawner_options_rejects_value_option_without_value() -> None:
    module = _load_ros2_control_launch_module()

    with pytest.raises(ValueError, match='requires a value'):
        module._resolve_spawner_options('spawner_options', '--inactive --switch-timeout')


def test_resolve_controller_remappings_accepts_json_list() -> None:
    module = _load_ros2_control_launch_module()

    assert module._resolve_controller_remappings(
        'robot_mima_controller_remappings', '[["~/reference", "cmd_vel"], ["~/odometry", "odom"]]'
    ) == [('~/reference', 'cmd_vel'), ('~/odometry', 'odom')]


def test_resolve_controller_remappings_accepts_empty_json_list() -> None:
    module = _load_ros2_control_launch_module()

    assert module._resolve_controller_remappings('robot_mima_controller_remappings', '[]') == []


def test_resolve_controller_remappings_accepts_json_null() -> None:
    module = _load_ros2_control_launch_module()

    assert module._resolve_controller_remappings('robot_mima_controller_remappings', 'null') is None


def test_resolve_controller_remappings_rejects_invalid_json_with_argument_name() -> None:
    module = _load_ros2_control_launch_module()

    with pytest.raises(ValueError, match='robot_mima_controller_remappings'):
        module._resolve_controller_remappings('robot_mima_controller_remappings', '')


def test_to_controller_remap_args_accepts_empty_values() -> None:
    module = _load_ros2_control_launch_module()

    assert module._to_controller_remap_args(None) == ''
    assert module._to_controller_remap_args([]) == ''


def test_to_controller_remap_args_converts_pairs_to_controller_ros_args_string() -> None:
    module = _load_ros2_control_launch_module()

    assert (
        module._to_controller_remap_args(
            [('~/reference', 'cmd_vel'), ('~/odometry', 'odom'), ('~/controller_state', 'state')]
        )
        == '--remap ~/reference:=cmd_vel --remap ~/odometry:=odom --remap ~/controller_state:=state'
    )


def test_join_controller_ros_args_skips_empty_fragments() -> None:
    module = _load_ros2_control_launch_module()

    assert (
        module._join_controller_ros_args('--ros-args --param use_sim_time:=true', '', '--remap ~/reference:=cmd_vel')
        == '--ros-args --param use_sim_time:=true --remap ~/reference:=cmd_vel'
    )


def _load_ros2_control_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_ros2_control.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_ros2_control_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
