import importlib.util
from pathlib import Path
from types import ModuleType

from conftest import PACKAGE_DIR
from launch import LaunchContext


def test_build_xacro_command_quotes_ros2_control_config_file(tmp_path) -> None:
    module = _load_robot_state_publisher_launch_module()
    xacro_file = tmp_path / 'robot.xacro'
    robot_sim_file = tmp_path / 'simulation.yaml'
    ros2_control_config_file = tmp_path / 'params with spaces.yaml'

    for path in (xacro_file, robot_sim_file, ros2_control_config_file):
        path.touch()

    command = module._build_xacro_command(str(xacro_file), '', str(robot_sim_file), str(ros2_control_config_file))

    assert module._quote_xarg_value_if_needed(str(ros2_control_config_file)) in command


def test_launch_node_passes_rendered_params_file_to_node_and_xacro(monkeypatch, tmp_path) -> None:
    module = _load_robot_state_publisher_launch_module()
    package_share = tmp_path / 'robot_mima_mkv30'
    xacro_file = package_share / 'urdf' / 'models' / 'model_base.xacro'
    params_file = tmp_path / 'params.yaml'
    xacro_file.parent.mkdir(parents=True)
    xacro_file.touch()
    params_file.write_text('/**:\n  ros__parameters: {}\n', encoding='utf-8')

    captured: dict[str, object] = {}

    def fake_render_params_file(params_file: str, ctx: object, output_path: Path) -> None:
        del ctx
        Path(output_path).write_text(Path(params_file).read_text(encoding='utf-8'), encoding='utf-8')

    def fake_parameter_file(params_file: str, allow_substs: bool) -> dict[str, object]:
        captured['parameter_file'] = params_file
        captured['parameter_file_allow_substs'] = allow_substs
        return {}

    def fake_build_xacro_command(
        xacro_file: str, robot_xacro_args_file: str, robot_sim_file: str, ros2_control_config_file: str
    ) -> list[str]:
        del xacro_file, robot_xacro_args_file, robot_sim_file
        captured['ros2_control_config_file'] = ros2_control_config_file
        return []

    class FakeNode:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

    monkeypatch.setattr(module, 'get_package_share_directory', lambda package_name: str(package_share))
    monkeypatch.setattr(module.rlh, 'render_params_file', fake_render_params_file)
    monkeypatch.setattr(module, 'ParameterFile', fake_parameter_file)
    monkeypatch.setattr(module, '_build_xacro_command', fake_build_xacro_command)
    monkeypatch.setattr(module, 'Node', FakeNode)

    context = LaunchContext()
    context.launch_configurations.update(
        {
            'robot_rsp_params_file': str(params_file),
            'robot_rsp_params_file_allow_substs': 'True',
            'robot_model': 'base',
            'robot_xacro_args_file': '',
            'robot_rsp_node_args': '{}',
            'robot_sim_file': '',
            'use_sim_time': 'False',
        }
    )

    module._launch_node(context)

    assert captured['parameter_file_allow_substs'] is False
    assert captured['parameter_file'] == captured['ros2_control_config_file']
    assert captured['parameter_file'] != str(params_file)


def test_quote_xacro_argument_value_uses_shell_quoting_when_needed() -> None:
    module = _load_robot_state_publisher_launch_module()

    assert module._quote_xarg_value_if_needed('plain_value') == 'plain_value'
    assert module._quote_xarg_value_if_needed('') == "''"
    assert module._quote_xarg_value_if_needed('value with spaces') == "'value with spaces'"
    assert module._quote_xarg_value_if_needed('value "with quotes"') == '\'value "with quotes"\''


def _load_robot_state_publisher_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_robot_state_publisher.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_robot_state_publisher_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
