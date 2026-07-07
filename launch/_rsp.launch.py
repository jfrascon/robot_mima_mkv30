import shlex
from pathlib import Path
from typing import Any

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile, ParameterValue
from robot_mima_mkv30.model_utils import get_models


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal robot_state_publisher launch description for one robot model.

    This launch file is meant to be included by `robot.launch.py`, not to be
    used as the user entry point for the package.

    The public robot launch file is responsible for passing the selected `robot_model` and
    the model-specific `params_file`. If this launch file is called directly,
    the caller must also pass `params_file`, `params_file_allow_substs`, and
    `use_sim_time` explicitly.
    """

    # Launch arguments with no default value must be provided by the caller.
    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
        DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model to publish'),
        DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
        DeclareLaunchArgument('params_file', description='Path to params file'),
        DeclareLaunchArgument(
            'params_file_allow_substs',
            choices=['True', 'true', 'False', 'false'],
            description='Allow ROS launch substitutions in params_file',
        ),
        DeclareLaunchArgument(
            'use_sim_time', choices=['True', 'true', 'False', 'false'], description='Use simulation clock if true'
        ),
        DeclareLaunchArgument(
            'model_xacro_args_file',
            default_value='',
            description='Path to the YAML file with xacro arguments loaded from configuration.',
        ),
        DeclareLaunchArgument(
            'sim_file',
            default_value='',
            description='Path to the simulation YAML. It is used only when use_sim_time is true.',
        ),
        DeclareLaunchArgument(
            'node_arguments',
            default_value='{"output": "both", "respawn": false}',
            description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
        ),
        rlh.SetRobotNamespace(
            namespace=LaunchConfiguration('namespace'),
            robot_name=LaunchConfiguration('robot_name'),
            robot_namespace_key='robot_namespace',
        ),
        rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), robot_prefix_key='robot_prefix'),
        OpaqueFunction(function=_launch_node),
    ]

    return LaunchDescription(ldes)


def _build_xacro_command(ctx: LaunchContext) -> list[Any]:
    """
    Build the xacro command list used to generate `robot_description`.

    The command always passes launch-provided xacro arguments such as namespace,
    robot_name, sim_file, and ros2_control_config_file directly. It then appends
    the optional xacro arguments loaded from `model_xacro_args_file`.
    """
    robot_model = LaunchConfiguration('robot_model').perform(ctx)

    # Get the xacro file for the selected model.
    xacro_file = Path(get_package_share_directory('robot_mima_mkv30')).joinpath(
        'urdf', 'models', f'model_{robot_model}.xacro'
    )

    if not xacro_file.is_file():
        raise FileNotFoundError(f"File '{xacro_file}' does not exist.")

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    if not use_sim_time_bool:
        sim_file = ''
    else:
        sim_file = LaunchConfiguration('sim_file').perform(ctx)

    model_xacro_args_file = LaunchConfiguration('model_xacro_args_file').perform(ctx)

    # The following xacro arguments are always passed directly by the launch files:
    # namespace, robot_name, sim_file, and ros2_control_config_file.
    # These xacro arguments are runtime arguments.
    # The rest of the xacro arguments are loaded from `model_xacro_args_file`, which is an optional
    # YAML file.
    # They configure model details such as optional sensors, visuals, collisions, inertias, and mesh
    # choices.
    # These values may change during testing and development, so it is convenient to keep them
    # in a separate YAML file.
    model_xacro_args = _load_model_xacro_args(model_xacro_args_file)

    cmd: list[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        str(xacro_file),
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
        ' ros2_control_config_file:=',
        LaunchConfiguration('params_file'),
        ' sim_file:=',
        _quote_xarg_value_if_needed(sim_file),
    ]

    # Add xacro arguments loaded from model_xacro_args_file.
    # Values are shell-quoted when needed so xacro receives each value as one token.
    for arg_name, arg_value in model_xacro_args.items():
        if arg_value is None:
            arg_value = ''
        elif isinstance(arg_value, (bool, int, float, str)):
            arg_value = str(arg_value)
        else:
            raise TypeError(f"Model xacro argument '{arg_name}' must be a YAML scalar, got {type(arg_value).__name__}.")

        cmd.extend([' ', f'{arg_name}:=', _quote_xarg_value_if_needed(arg_value)])

    return cmd


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch robot_state_publisher for the selected model.
    """

    # launch_ros.parameter_descriptions.ParameterFile accepts param_file as FilePath or
    # SomeSubstitutionsType, so params_file can stay as a LaunchConfiguration and be resolved later.
    # The same class also annotates allow_substs as bool or SomeSubstitutionsType, but Jazzy
    # validates that argument as a bool when the ParameterFile object is constructed. Because of
    # that runtime validation, params_file_allow_substs must be evaluated before it is passed as
    # allow_substs.
    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    parameters: list[Any] = [
        # When params_file_allow_substs is true, the caller must provide every launch
        # context key used by the parameter file. If it is false, the file is loaded
        # without expanding launch substitutions.
        ParameterFile(LaunchConfiguration('params_file'), allow_substs=params_file_allow_substs),
        {
            'robot_description': ParameterValue(Command(_build_xacro_command(ctx)), value_type=str),
            # robot_description is always published on a topic.
            'use_robot_description_topic': True,
            # Frame prefixes are already part of the link and joint names generated by xacro.
            'frame_prefix': '',
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        },
    ]

    ldes: list[LaunchDescriptionEntity] = [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=parameters,
            **rlh.resolve_node_arguments(
                LaunchConfiguration('node_arguments').perform(ctx),
                default_arguments={
                    'name': 'robot_state_publisher',
                    'output': 'screen',
                    'emulate_tty': True,
                    'respawn': False,
                },
            ),
        )
    ]

    return ldes


def _load_model_xacro_args(model_xacro_args_file: str) -> dict[str, Any]:
    """
    Load xacro arguments from the optional YAML configuration file.

    An empty `model_xacro_args_file` means that no xacro arguments are loaded from YAML.

    This function does not catch exceptions raised by `rlh.read_yaml_file`.
    Resolution, filesystem, encoding, and YAML parsing errors propagate and fail the launch.
    See `ros2_launch_helpers.read_yaml_file` for the exact exception contract.

    :param model_xacro_args_file: Path or URI to the YAML file with xacro arguments loaded from
        configuration.
    :return: Mapping from xacro argument name to xacro argument value.
    :raises TypeError: If the YAML top level is not a mapping or if a key is not a string.
    :raises ValueError: If the YAML file sets a launch-provided xacro argument.
    """
    if not model_xacro_args_file:
        return {}

    resolved_model_xacro_args_file, model_xacro_args = rlh.read_yaml_file(model_xacro_args_file)

    # rlh.read_yaml_file returns None when the YAML file contains only comments or whitespace.
    if model_xacro_args is None:
        model_xacro_args = {}

    if not isinstance(model_xacro_args, dict):
        raise TypeError(
            f"Model xacro args file '{resolved_model_xacro_args_file}' must contain a YAML "
            f'mapping at the top level, got {type(model_xacro_args).__name__}.'
        )

    for arg_name in model_xacro_args:
        # Argument names must be strings because they are used as xacro argument names.
        if not isinstance(arg_name, str):
            raise TypeError(
                f"Model xacro args file '{resolved_model_xacro_args_file}' contains a non-string key "
                f'{arg_name!r} of type {type(arg_name).__name__}.'
            )
        # There are some xacro arguments that are always passed directly by the launch files and
        # must not be set in the YAML file.
        if arg_name in ('namespace', 'robot_name', 'sim_file', 'ros2_control_config_file'):
            raise ValueError(
                f"Model xacro args file '{resolved_model_xacro_args_file}' must not set the argument '{arg_name}'"
            )

    return model_xacro_args


def _quote_xarg_value_if_needed(raw_value: str) -> str:
    """
    Quote xacro argument values when the shell would otherwise split or reinterpret them.
    """
    quoted_value = shlex.quote(raw_value)
    return quoted_value if quoted_value != raw_value else raw_value
