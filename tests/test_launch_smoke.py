import pytest
from conftest import run_bash


@pytest.mark.parametrize(
    ('launch_file', 'launch_args', 'expected_text'),
    [
        (
            'model_base.launch.py',
            'params_file_allow_substs:=True use_sim_time:=True '
            'bridge_file:=$(ros2 pkg prefix robot_mima_mkv30)/share/robot_mima_mkv30/config/'
            'model_base/example_bridge.yaml '
            'local_odometry_frame:=odom',
            'Robot initialized',
        ),
        (
            'model_sensors1.launch.py',
            'robot_name:=mima_mkv30 params_file_allow_substs:=True use_sim_time:=True '
            'bridge_file:=$(ros2 pkg prefix robot_mima_mkv30)/share/robot_mima_mkv30/config/'
            'model_sensors1/example_bridge.yaml '
            'local_odometry_frame:=odom',
            'Creating GZ->ROS Bridge:',
        ),
    ],
)
def test_robot_launch_smoke(launch_file: str, launch_args: str, expected_text: str) -> None:
    result = run_bash(f'timeout --signal=INT 8s ros2 launch robot_mima_mkv30 {launch_file} {launch_args}')

    output = result.stdout + result.stderr

    # timeout returns 124 when the launch keeps running as expected until interrupted.
    assert result.returncode in {0, 124}, output
    assert 'process started with pid' in output, output
    assert expected_text in output, output
