"""
Helpers to expose public robot models and prepare launch-time parameter files.

The package publishes robot models through files named
`urdf/models/model_<robot_model>.xacro`. The short model name is the part after
`model_`; for example, `model_base.xacro` publishes model `base`.
"""

from pathlib import Path
from tempfile import gettempdir

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch.actions import SetLaunchConfiguration
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution

from launch import LaunchDescriptionEntity

MODEL_FILE_PREFIX = 'model_'


def get_models() -> list[str]:
    """
    Return the public robot models provided by this package.
    """
    urdf_dir = _get_urdf_dir()

    return sorted(
        path.stem.removeprefix(MODEL_FILE_PREFIX)
        for path in urdf_dir.glob(f'{MODEL_FILE_PREFIX}*.xacro')
        if path.is_file()
    )


def process_params_file(ctx: LaunchContext, params_file_key: str = 'params_file') -> list[LaunchDescriptionEntity]:
    """
    Prepare the robot parameter YAML path for child launch files and xacro.

    `params_file_key` identifies the single robot configuration file used by
    robot_state_publisher, the ROS-GZ bridge, ros2_control, and the
    gz_ros2_control plugin path written into the URDF. That file may contain
    ROS launch substitutions such as `$(var robot_prefix)`,
    `$(var robot_odometry_frame)`, `$(var robot_base_frame)`, or fixed robot
    model values like `$(var robot_wheelbase)`.

    When `params_file_allow_substs` is true, this function renders the file once
    with the standard launch_ros parameter-file substitution engine and stores a
    stable rendered copy in `/tmp`. The child launch files then receive that
    rendered path with `params_file_allow_substs` set to false, and xacro passes
    the same rendered path to Gazebo as `ros2_control_config_file`.

    When `params_file_allow_substs` is false, this function only resolves the
    input path and stores that resolved path back in `params_file_key`. No YAML
    rendering is done, so no extra launch context keys are required.
    """
    params_file = rlh.resolve_file(LaunchConfiguration(params_file_key).perform(ctx))

    if not params_file:
        raise RuntimeError('params_file is required to prepare the robot parameters YAML file.')

    if not Path(params_file).is_file():
        raise FileNotFoundError(f"Params file '{params_file}' does not exist.")

    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    if not params_file_allow_substs:
        # Even without rendering, replace the launch value with the resolved filesystem path.
        # This keeps downstream launch actions from receiving package://, file://, or '~' paths
        # after this wrapper tells them that substitutions are already disabled.
        return [SetLaunchConfiguration(params_file_key, params_file)]

    flattened_namespace = rlh.flatten_namespace(LaunchConfiguration('robot_namespace').perform(ctx), '_')
    rendered_params_file = Path(gettempdir()).joinpath(f'{flattened_namespace}_robot_params.yaml')

    rlh.render_params_file(params_file, rendered_params_file, ctx)

    return [SetLaunchConfiguration(params_file_key, str(rendered_params_file))]


def _get_urdf_dir() -> Path:
    """
    Return the installed directory that stores public model Xacro files.
    """
    urdf_dir = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('urdf', 'models')

    if not urdf_dir.is_dir():
        raise FileNotFoundError(f'URDF directory {urdf_dir!r} not found.')

    return urdf_dir
