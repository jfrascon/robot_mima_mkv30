from pathlib import Path

from conftest import PACKAGE_DIR, run_bash


def test_model_base_expands_to_valid_urdf(tmp_path: Path) -> None:
    urdf_path = tmp_path / 'model_base.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'models' / 'model_base.xacro'

    result = run_bash(f'xacro "{xacro_path}" > "{urdf_path}" && check_urdf "{urdf_path}"')
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert urdf_path.is_file(), output
    assert 'Successfully Parsed XML' in output, output


def test_model_base_sim_expands_to_valid_urdf(tmp_path: Path) -> None:
    urdf_path = tmp_path / 'model_base_sim.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'models' / 'model_base.xacro'
    controllers = PACKAGE_DIR / 'config' / 'model_base' / 'example_params.yaml'

    result = run_bash(
        f'xacro "{xacro_path}" use_sim_mode:=True ros2_control_config_file:="{controllers}" '
        f'> "{urdf_path}" && check_urdf "{urdf_path}"'
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert urdf_path.is_file(), output
    assert 'Successfully Parsed XML' in output, output
    assert 'gz_ros2_control/GazeboSimSystem' in urdf_path.read_text(encoding='utf-8')


def test_model_base_has_only_expected_wheel_meshes_and_no_sensors(tmp_path: Path) -> None:
    urdf_path = tmp_path / 'model_base.urdf'
    xacro_path = PACKAGE_DIR / 'urdf' / 'models' / 'model_base.xacro'

    result = run_bash(f'xacro "{xacro_path}" > "{urdf_path}"')
    output = result.stdout + result.stderr

    assert result.returncode == 0, output

    urdf = urdf_path.read_text(encoding='utf-8')
    expected_wheel_mesh = (
        'mesh filename="package://robotics_description/meshes/wheels/standard_wheels/rubber_wheel_3.stl"'
    )
    mesh_count = urdf.lower().count('mesh filename=')

    assert mesh_count == 4
    assert urdf.lower().count(expected_wheel_mesh) == 4

    forbidden_tokens = ['laser', 'lidar', 'camera', 'imu', 'ray', 'gpu_lidar']
    for token in forbidden_tokens:
        assert token not in urdf.lower()


def test_launch_show_args_lists_expected_arguments() -> None:
    result = run_bash('ros2 launch robot_mima_mkv30 model_base.launch.py --show-args')
    output = result.stdout + result.stderr

    assert result.returncode == 0, output
    assert "'use_sim_time'" in output, output
    assert "'robot_name'" in output, output
    assert "'params_file'" in output, output
    assert "'params_file_allow_substs'" in output, output
    assert "'controller_config_file'" not in output, output
