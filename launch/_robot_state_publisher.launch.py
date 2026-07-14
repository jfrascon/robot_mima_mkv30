import shlex
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetLaunchConfiguration
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile, ParameterValue
from robot_mima_mkv30.model_utils import get_models


def generate_launch_description() -> LaunchDescription:
    # Launch arguments with no default value must be provided by the caller.
    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model to publish'),
            DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
            DeclareLaunchArgument(
                'robot_rsp_params_file', description='Path to the complete robot parameter YAML file.'
            ),
            DeclareLaunchArgument(
                'robot_rsp_params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in robot_rsp_params_file',
            ),
            DeclareLaunchArgument(
                'use_sim_time',
                choices=['True', 'true', 'False', 'false'],
                description='Use ROS time from /clock if true.',
            ),
            DeclareLaunchArgument(
                'robot_xacro_args_file',
                default_value='',
                description='Path to the YAML file with xacro arguments loaded from configuration.',
            ),
            DeclareLaunchArgument(
                'robot_sim_file',
                default_value='',
                description=(
                    'Optional simulation YAML. Empty means the xacro model is built without simulation plugins.'
                ),
            ),
            DeclareLaunchArgument(
                'robot_rsp_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            rlh.RequireFile(path=LaunchConfiguration('robot_rsp_params_file')),
            # Insert `robot_type`, `robot_namespace` and `robot_prefix` into the launch context.
            # Their values can then be substituted in the parameter file if needed.
            SetLaunchConfiguration('robot_type', 'mima_mkv30'),
            rlh.SetRobotNamespace(
                namespace=LaunchConfiguration('namespace'),
                robot_name=LaunchConfiguration('robot_name'),
                output_context_key='robot_namespace',
            ),
            rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), output_context_key='robot_prefix'),
            OpaqueFunction(function=_launch_node),
        ]
    )


def _build_xacro_command(
    xacro_file: str, robot_xacro_args_file: str, robot_sim_file: str, ros2_control_config_file: str
) -> list[Any]:
    """
    Build the xacro command list used to generate `robot_description`.

    The command always passes launch-provided xacro arguments such as namespace,
    robot_name, robot_sim_file, and ros2_control_config_file directly. It then
    appends the optional xacro arguments loaded from `robot_xacro_args_file`.
    """
    if not xacro_file:
        raise ValueError('xacro_file must be a non-empty string.')

    if not Path(xacro_file).is_file():
        raise FileNotFoundError(f"File '{xacro_file}' does not exist.")

    if robot_xacro_args_file and not Path(robot_xacro_args_file).is_file():
        raise FileNotFoundError(f"File '{robot_xacro_args_file}' does not exist.")

    if robot_sim_file and not Path(robot_sim_file).is_file():
        raise FileNotFoundError(f"File '{robot_sim_file}' does not exist.")

    # If a simulation file is provided, then the model includes simulation-specific elements such
    # as plugins.
    # One of those plugins is the ros2_control plugin, which requires a ros2_control configuration
    # file.
    # In that case, ensure that the ros2_control configuration file is provided and exists.
    if robot_sim_file:
        if not ros2_control_config_file:
            raise ValueError(
                'ros2_control_config_file must be provided when robot_sim_file is provided. '
                'The ros2_control configuration file is required by the ros2_control plugin.'
            )

        if not Path(ros2_control_config_file).is_file():
            raise FileNotFoundError(f"File '{ros2_control_config_file}' does not exist.")
    else:
        # If a simulation file is not provided, the ros2_control_config_file is not used in the
        # robot model. Therefore, it does not matter whether a file is passed or whether it exists.
        # However, to be explicit with the intention of not using a ros2_control configuration file
        # when not using simulation, pass an empty string to xacro.
        ros2_control_config_file = ''

    # The following xacro arguments are always passed directly by the launch files:
    # namespace, robot_name, robot_sim_file, and ros2_control_config_file.
    # These xacro arguments are runtime arguments.
    # The rest of the xacro arguments are loaded from `robot_xacro_args_file`, which is an optional
    # YAML file.
    # They configure model details such as optional sensors, visuals, collisions, inertias, and mesh
    # choices.
    # These values may change during testing and development, so it is convenient to keep them
    # in a separate YAML file.
    robot_xacro_args = _load_robot_xacro_args(robot_xacro_args_file)

    cmd: list[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        xacro_file,
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
        ' ros2_control_config_file:=',
        _quote_xarg_value_if_needed(ros2_control_config_file),
        ' sim_file:=',
        _quote_xarg_value_if_needed(robot_sim_file),
    ]

    # Add xacro arguments loaded from robot_xacro_args_file.
    # Values are shell-quoted when needed so xacro receives each value as one token.
    for arg_name, arg_value in robot_xacro_args.items():
        if arg_value is None:
            arg_value = ''
        elif isinstance(arg_value, (bool, int, float, str)):
            arg_value = str(arg_value)
        else:
            raise TypeError(f"Robot xacro argument '{arg_name}' must be a YAML scalar, got {type(arg_value).__name__}.")

        cmd.extend([' ', f'{arg_name}:=', _quote_xarg_value_if_needed(arg_value)])

    return cmd


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:

    # When substitutions are allowed, render the parameter file before using it.
    # robot_state_publisher and xacro must receive the same parameter file path.
    params_file = LaunchConfiguration('robot_rsp_params_file').perform(ctx)

    if perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('robot_rsp_params_file_allow_substs'), bool), bool
    ):
        # Create a temporary file to hold the rendered parameters.
        with NamedTemporaryFile(prefix='params_', suffix='.yaml', delete=False) as temp_file:
            output_path = Path(temp_file.name)
        rlh.render_params_file(params_file, ctx, output_path)
        params_file = str(output_path)

    robot_model = LaunchConfiguration('robot_model').perform(ctx)

    # Get the xacro file for the selected model.
    xacro_file = Path(get_package_share_directory('robot_mima_mkv30')).joinpath(
        'urdf', 'models', f'model_{robot_model}.xacro'
    )

    # Get the robot xacro arguments file from the launch configuration, if present.
    # It is an optional YAML file that contains xacro arguments loaded from configuration.
    robot_xacro_args_file = LaunchConfiguration('robot_xacro_args_file').perform(ctx)
    robot_sim_file = LaunchConfiguration('robot_sim_file').perform(ctx)

    return [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=[
                ParameterFile(params_file, allow_substs=False),
                {
                    'robot_description': ParameterValue(
                        Command(
                            _build_xacro_command(str(xacro_file), robot_xacro_args_file, robot_sim_file, params_file)
                        ),
                        value_type=str,
                    ),
                    # robot_description is always published on a topic.
                    'use_robot_description_topic': True,
                    # Link and joint names generated by xacro already include their frame prefixes.
                    'frame_prefix': '',
                    'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool),
                },
            ],
            **rlh.resolve_node_arguments(
                LaunchConfiguration('robot_rsp_node_args').perform(ctx), extra_rejected_arguments={'namespace'}
            ),
        )
    ]


def _load_robot_xacro_args(robot_xacro_args_file: str) -> dict[str, Any]:
    """
    Load xacro arguments from the optional YAML configuration file.

    An empty `robot_xacro_args_file` means that no xacro arguments are loaded from YAML.

    This function does not catch exceptions raised by `rlh.read_yaml_file`.
    Resolution, filesystem, encoding, and YAML parsing errors propagate and fail the launch.
    See `ros2_launch_helpers.read_yaml_file` for the exact exception contract.

    :param robot_xacro_args_file: Path or URI to the YAML file with xacro arguments loaded from
        configuration.
    :return: Mapping from xacro argument name to xacro argument value.
    :raises TypeError: If the YAML top level is not a mapping or if a key is not a string.
    :raises ValueError: If the YAML file sets a launch-provided xacro argument.
    """
    if not robot_xacro_args_file:
        return {}

    resolved_robot_xacro_args_file, robot_xacro_args = rlh.read_yaml_file(robot_xacro_args_file)

    # rlh.read_yaml_file returns None when the YAML file contains only comments or whitespace.
    if robot_xacro_args is None:
        robot_xacro_args = {}

    if not isinstance(robot_xacro_args, dict):
        raise TypeError(
            f"Robot xacro args file '{resolved_robot_xacro_args_file}' must contain a YAML "
            f'mapping at the top level, got {type(robot_xacro_args).__name__}.'
        )

    for arg_name in robot_xacro_args:
        # Argument names must be strings because they are used as xacro argument names.
        if not isinstance(arg_name, str):
            raise TypeError(
                f"Robot xacro args file '{resolved_robot_xacro_args_file}' contains a non-string key "
                f'{arg_name!r} of type {type(arg_name).__name__}.'
            )
        # There are some xacro arguments that are always passed directly by the launch files and
        # must not be set in the YAML file.
        if arg_name in ('namespace', 'robot_name', 'sim_file', 'ros2_control_config_file'):
            raise ValueError(
                f"Robot xacro args file '{resolved_robot_xacro_args_file}' must not set the argument '{arg_name}'"
            )

    return robot_xacro_args


def _quote_xarg_value_if_needed(raw_value: str) -> str:
    """
    Quote xacro argument values when the shell would otherwise split or reinterpret them.
    """
    quoted_value = shlex.quote(raw_value)
    return quoted_value if quoted_value != raw_value else raw_value
