import importlib.util
from types import ModuleType

import pytest
from conftest import PACKAGE_DIR
from launch.launch_context import LaunchContext


def test_resolve_controller_log_args_accepts_empty_value() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = ''

    assert module._resolve_controller_log_args(ctx, 'controller_log_args') == ''


def test_resolve_controller_log_args_accepts_general_and_logger_levels() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = (
        '--log-level info --log-level botzilla.mima_controller.abc:=debug'
    )

    assert (
        module._resolve_controller_log_args(ctx, 'controller_log_args')
        == '--log-level info --log-level botzilla.mima_controller.abc:=debug'
    )


def test_resolve_controller_log_args_rejects_other_ros_args() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = '--param use_sim_time:=false'

    with pytest.raises(ValueError, match='--param'):
        module._resolve_controller_log_args(ctx, 'controller_log_args')


def test_resolve_controller_log_args_rejects_missing_log_level_value() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = '--log-level'

    with pytest.raises(ValueError, match='requires a value'):
        module._resolve_controller_log_args(ctx, 'controller_log_args')


def test_resolve_controller_log_args_rejects_unknown_log_level() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = '--log-level verbose'

    with pytest.raises(ValueError, match='verbose'):
        module._resolve_controller_log_args(ctx, 'controller_log_args')


def test_resolve_controller_log_args_rejects_empty_logger_name() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['controller_log_args'] = '--log-level :=debug'

    with pytest.raises(ValueError, match='empty logger name'):
        module._resolve_controller_log_args(ctx, 'controller_log_args')


def test_resolve_spawner_options_accepts_exposed_flags_and_value_options() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['spawner_options'] = (
        '--inactive --switch-timeout 60.0 --service-call-timeout 15.0 --no-switch-asap'
    )

    assert module._resolve_spawner_options(ctx, 'spawner_options') == [
        '--inactive',
        '--switch-timeout',
        '60.0',
        '--service-call-timeout',
        '15.0',
        '--no-switch-asap',
    ]


def test_resolve_spawner_options_rejects_controller_ros_args() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['spawner_options'] = (
        '--inactive --controller-ros-args "--ros-args --param use_sim_time:=true"'
    )

    with pytest.raises(ValueError, match='--controller-ros-args'):
        module._resolve_spawner_options(ctx, 'spawner_options')


def test_resolve_spawner_options_rejects_value_option_without_value() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['spawner_options'] = '--inactive --switch-timeout'

    with pytest.raises(ValueError, match='requires a value'):
        module._resolve_spawner_options(ctx, 'spawner_options')


def test_merge_controller_remappings_overrides_by_from_side_and_keeps_defaults() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['mima_controller_remappings'] = '[["~/reference","cmd_vel_nav"]]'

    assert (
        module._merge_controller_remappings(
            ctx,
            '[["~/reference","cmd_vel"],["~/odometry","odom"],["~/controller_state","state"]]',
            'mima_controller_remappings',
        )
        == '--remap ~/reference:=cmd_vel_nav --remap ~/odometry:=odom --remap ~/controller_state:=state'
    )


def test_merge_controller_remappings_appends_new_from_side() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['mima_controller_remappings'] = '[["~/extra","extra_topic"]]'

    assert (
        module._merge_controller_remappings(ctx, '[["~/reference","cmd_vel"]]', 'mima_controller_remappings')
        == '--remap ~/reference:=cmd_vel --remap ~/extra:=extra_topic'
    )


def test_merge_controller_remappings_accepts_empty_json_list_override() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['mima_controller_remappings'] = '[]'

    assert (
        module._merge_controller_remappings(ctx, '[["~/reference","cmd_vel"]]', 'mima_controller_remappings')
        == '--remap ~/reference:=cmd_vel'
    )


def test_merge_controller_remappings_rejects_empty_override_value() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['mima_controller_remappings'] = ''

    with pytest.raises(RuntimeError, match='mima_controller_remappings'):
        module._merge_controller_remappings(ctx, '[["~/reference","cmd_vel"]]', 'mima_controller_remappings')


def test_merge_controller_remappings_ignores_null_override_value() -> None:
    module = _load_ros2_control_launch_module()
    ctx = LaunchContext()
    ctx.launch_configurations['mima_controller_remappings'] = 'null'

    assert (
        module._merge_controller_remappings(ctx, '[["~/reference","cmd_vel"]]', 'mima_controller_remappings')
        == '--remap ~/reference:=cmd_vel'
    )


def _load_ros2_control_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_ros2_control.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_ros2_control_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
