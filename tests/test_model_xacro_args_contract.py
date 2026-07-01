import re
from pathlib import Path

import yaml
from conftest import PACKAGE_DIR

from robot_mima_mkv30.model_utils import get_models

LAUNCH_SCOPED_XACRO_ARGS = {'sim_file', 'namespace', 'robot_name', 'ros2_control_config_file'}

BASE_MODEL_XACRO_ARGS = {
    'chassis_use_visual',
    'chassis_use_inertial',
    's_wheel_use_visual',
    's_wheel_use_inertial',
    's_wheel_use_v_mesh',
    'wheel_use_visual',
    'wheel_use_v_mesh',
    'wheel_use_inertial',
    'fork_use_visual',
    'fork_use_inertial',
}

SENSORS1_MODEL_XACRO_ARGS = BASE_MODEL_XACRO_ARGS | {
    'use_front_lidar2d',
    'front_lidar2d_use_visual',
    'front_lidar2d_use_collision',
    'front_lidar2d_use_v_mesh',
    'front_lidar2d_v_mesh_use_low_res',
    'front_lidar2d_use_c_mesh',
    'front_lidar2d_c_mesh_use_low_res',
    'use_back_lidar2d',
    'back_lidar2d_use_visual',
    'back_lidar2d_use_collision',
    'back_lidar2d_use_v_mesh',
    'back_lidar2d_v_mesh_use_low_res',
    'back_lidar2d_use_c_mesh',
    'back_lidar2d_c_mesh_use_low_res',
    'use_left_lidar2d',
    'left_lidar2d_use_visual',
    'left_lidar2d_use_collision',
    'left_lidar2d_use_v_mesh',
    'left_lidar2d_v_mesh_use_low_res',
    'left_lidar2d_use_c_mesh',
    'left_lidar2d_c_mesh_use_low_res',
    'use_right_lidar2d',
    'right_lidar2d_use_visual',
    'right_lidar2d_use_collision',
    'right_lidar2d_use_v_mesh',
    'right_lidar2d_v_mesh_use_low_res',
    'right_lidar2d_use_c_mesh',
    'right_lidar2d_c_mesh_use_low_res',
    'use_front_top_lidar3d',
    'front_top_lidar3d_use_visual',
    'front_top_lidar3d_use_collision',
    'front_top_lidar3d_use_v_mesh',
    'front_top_lidar3d_v_mesh_use_low_res',
    'front_top_lidar3d_use_c_mesh',
    'front_top_lidar3d_c_mesh_use_low_res',
    'use_left_top_lidar3d',
    'left_top_lidar3d_use_visual',
    'left_top_lidar3d_use_collision',
    'use_fork_board_camera',
    'fork_board_camera_use_visual',
    'fork_board_camera_use_collision',
    'fork_board_camera_use_v_mesh',
    'fork_board_camera_v_mesh_use_low_res',
    'fork_board_camera_use_c_mesh',
    'fork_board_camera_c_mesh_use_low_res',
    'use_chassis_imu',
}


def _load_model_xacro_args(robot_model: str) -> dict[str, object]:
    model_xacro_args_file = PACKAGE_DIR / 'config' / f'model_{robot_model}' / 'default_model_xacro_args.yaml'

    with model_xacro_args_file.open('r', encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}

    assert isinstance(data, dict)
    return data


def _xacro_arg_names(xacro_file: Path) -> set[str]:
    pattern = re.compile(r'<xacro:arg\s+name="([^"]+)"')
    return set(pattern.findall(xacro_file.read_text(encoding='utf-8')))


def test_common_xacro_exposes_launch_and_base_model_arguments() -> None:
    common_xacro = PACKAGE_DIR / 'urdf' / 'includes' / 'common.xacro'

    assert _xacro_arg_names(common_xacro) == LAUNCH_SCOPED_XACRO_ARGS | BASE_MODEL_XACRO_ARGS


def test_default_model_xacro_args_match_the_yaml_contract() -> None:
    base_model_xacro_args = _load_model_xacro_args('base')
    sensors1_model_xacro_args = _load_model_xacro_args('sensors1')

    assert set(base_model_xacro_args) == BASE_MODEL_XACRO_ARGS
    assert set(sensors1_model_xacro_args) == SENSORS1_MODEL_XACRO_ARGS
    assert base_model_xacro_args.items() <= sensors1_model_xacro_args.items()
    assert not LAUNCH_SCOPED_XACRO_ARGS.intersection(base_model_xacro_args)
    assert not LAUNCH_SCOPED_XACRO_ARGS.intersection(sensors1_model_xacro_args)


def test_model_utils_lists_public_robot_models() -> None:
    assert get_models() == ['base', 'sensors1']


def test_sensors1_model_declares_sensor_model_arguments() -> None:
    sensors1_xacro = PACKAGE_DIR / 'urdf' / 'models' / 'model_sensors1.xacro'

    assert _xacro_arg_names(sensors1_xacro) == SENSORS1_MODEL_XACRO_ARGS - BASE_MODEL_XACRO_ARGS


def test_xargs_yaml_contract_is_removed() -> None:
    xargs_dir = PACKAGE_DIR / 'robot_mima_mkv30' / 'xargs'

    assert not list(xargs_dir.glob('*.yaml'))
