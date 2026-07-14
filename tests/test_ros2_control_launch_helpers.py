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


def test_resolve_spawner_options_reports_unclosed_quotes_with_argument_name() -> None:
    module = _load_ros2_control_launch_module()

    with pytest.raises(ValueError, match='robot_mima_controller_spawner_options'):
        module._resolve_spawner_options('robot_mima_controller_spawner_options', '--switch-timeout "30.0')


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


def test_get_spawner_arguments_builds_expected_controller_cli() -> None:
    module = _load_ros2_control_launch_module()

    assert module._get_spawner_arguments(
        True,
        '/ifc/mima_mkv30_1/controller_manager',
        'mima_controller',
        ['--switch-timeout', '30.0'],
        [('~/reference', 'cmd_vel'), ('~/odometry', 'odom')],
    ) == [
        '--controller-manager',
        '/ifc/mima_mkv30_1/controller_manager',
        '--switch-timeout',
        '30.0',
        '--controller-ros-args',
        '--ros-args --param use_sim_time:=True --remap ~/reference:=cmd_vel --remap ~/odometry:=odom',
        'mima_controller',
    ]


def _load_ros2_control_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_ros2_control.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_ros2_control_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
