import os
from pathlib import Path
from typing import Any

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, FindExecutable, LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile, ParameterValue

from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal robot_state_publisher launch description for one model
    wrapper.

    This launch file is meant to be included by `model_*.launch.py`, not to be
    used as the user entry point for the package.

    The model wrapper is responsible for passing the selected `robot_model` and
    the model-specific `params_file`. If this launch file is called directly,
    the caller must also pass `params_file`, `params_file_allow_substs`, and
    `use_sim_time` explicitly.
    """
    # Launch arguments with no default value must be provided by the caller.
    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
        DeclareLaunchArgument('robot_model', choices=_get_models(), description='Robot model to publish'),
        DeclareLaunchArgument('robot_name', description="Robot's name"),
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
        DeclareLaunchArgument('node_name', default_value='robot_state_publisher', description='Node name'),
        DeclareLaunchArgument('node_remappings_map', default_value='{}', description=rlh.REMAPPINGS_DESC),
        DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
        DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
        OpaqueFunction(
            function=rlh.set_robot_namespace,
            kwargs={
                'namespace_key': 'namespace',
                'robot_name_key': 'robot_name',
                'robot_namespace_key': 'robot_namespace',
            },
        ),
        OpaqueFunction(
            function=rlh.set_robot_prefix, kwargs={'robot_name_key': 'robot_name', 'robot_prefix_key': 'robot_prefix'}
        ),
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
    xacro_file = os.path.join(
        get_package_share_directory('robot_mima_mkv30'), 'urdf', 'models', f'model_{robot_model}.xacro'
    )

    if not Path(xacro_file).is_file():
        raise FileNotFoundError(f"File '{xacro_file}' does not exist.")

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)
    model_xacro_args_file = LaunchConfiguration('model_xacro_args_file').perform(ctx)
    sim_file = LaunchConfiguration('sim_file').perform(ctx)

    if not use_sim_time_bool:
        sim_file = ''
    elif sim_file:
        sim_file = rlh.resolve_file(sim_file)

    # All values consumed by the xacro model are xacro arguments.
    #
    # Some xacro arguments are launch-provided arguments. They identify the
    # current robot instance or runtime context, so they are passed directly by
    # the launch files. Examples are `namespace`, `robot_name`, `sim_file`, and
    # `ros2_control_config_file`.
    #
    # Other xacro arguments are loaded from `model_xacro_args_file`. They
    # configure model details such as optional sensors, visuals, collisions,
    # inertias, and mesh choices. These values usually change together and are
    # easier to review in a YAML file, so the launch file loads them and passes
    # them to xacro as regular xacro arguments.
    model_xacro_args = _load_model_xacro_args(model_xacro_args_file)

    cmd: list[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        xacro_file,
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
        ' ros2_control_config_file:=',
        LaunchConfiguration('params_file'),
        ' sim_file:=',
        _quote_xarg_value_if_needed(sim_file),
    ]

    # Add xacro arguments loaded from model_xacro_args_file. Values containing
    # whitespace are quoted so xacro parses each value as one token.
    for arg_name, arg_value in model_xacro_args.items():
        if arg_value is None:
            arg_value = ''
        elif isinstance(arg_value, (bool, int, float, str)):
            arg_value = str(arg_value)
        else:
            raise TypeError(f"Model xacro argument '{arg_name}' must be a YAML scalar, got {type(arg_value).__name__}.")

        cmd.extend([' ', f'{arg_name}:=', _quote_xarg_value_if_needed(arg_value)])

    return cmd


def _get_models() -> list[str]:
    """
    Return the public robot model names available to robot_state_publisher.

    Public model xacro files are stored as `urdf/models/model_<robot_model>.xacro`.
    The launch argument uses the short model name, for example `base` or `sensors1`.
    """
    model_file_prefix = 'model_'
    urdf_dir = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('urdf', 'models')

    if not urdf_dir.is_dir():
        raise FileNotFoundError(f'URDF directory {urdf_dir!r} does not exist.')

    return sorted(
        path.stem.removeprefix(model_file_prefix)
        for path in urdf_dir.glob(f'{model_file_prefix}*.xacro')
        if path.is_file()
    )


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch robot_state_publisher for the selected model.
    """
    params_file = rlh.resolve_file(LaunchConfiguration('params_file').perform(ctx))

    if not Path(params_file).is_file():
        raise FileNotFoundError(f"Params file '{params_file}' does not exist.")

    # xacro reads the same prepared robot parameters file through the internal
    # `ros2_control_config_file` argument. Store the resolved path in the local
    # launch context before building the command so xacro receives that path.
    ctx.launch_configurations['params_file'] = params_file
    cmd = _build_xacro_command(ctx)

    # When params_file_allow_substs is true, the caller must provide every launch
    # context key used by the parameter file. If it is false, the file is loaded
    # without expanding launch substitutions.
    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    parameters: list[Any] = [
        ParameterFile(params_file, allow_substs=params_file_allow_substs),
        {
            'robot_description': ParameterValue(Command(cmd), value_type=str),
            # robot_description is always published on a topic.
            'use_robot_description_topic': True,
            # Frame prefixes are already part of the link and joint names generated by xacro.
            'frame_prefix': '',
            'use_sim_time': use_sim_time,
        },
    ]

    node_name = LaunchConfiguration('node_name').perform(ctx)

    if not rlh.is_valid_name(node_name):
        raise RuntimeError(f"The name of the node must be ASCII [A-Za-z0-9_] only: '{node_name}'")

    node_options, node_remappings, node_ros_arguments = rlh.resolve_node_launch_configs(
        [node_name],
        LaunchConfiguration('node_options_map').perform(ctx),
        LaunchConfiguration('node_logging_options_map').perform(ctx),
        LaunchConfiguration('node_remappings_map').perform(ctx),
    )

    return [
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name=node_name,
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=parameters,
            remappings=node_remappings[node_name],
            ros_arguments=node_ros_arguments[node_name],
            output=node_options[node_name]['output'],
            emulate_tty=node_options[node_name]['emulate_tty'],
            respawn=node_options[node_name]['respawn'],
            respawn_delay=node_options[node_name]['respawn_delay'],
        )
    ]


def _load_model_xacro_args(model_xacro_args_file: str) -> dict[str, Any]:
    """
    Load xacro arguments from the optional YAML configuration file.

    An empty `model_xacro_args_file` means that no xacro arguments are loaded from YAML.

    This function does not catch exceptions raised by `rlh.read_yaml_file`.
    Resolution, filesystem, encoding, and YAML parsing errors propagate and fail the launch.
    See `ros2_launch_helpers.read_yaml_file` for the exact exception contract.

    :param model_xacro_args_file: Path or URI to the YAML file with xacro arguments loaded from configuration.
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
            f"Model xacro args file '{resolved_model_xacro_args_file}' must contain a YAML mapping at the top level, "
            f'got {type(model_xacro_args).__name__}.'
        )

    for arg_name in model_xacro_args:
        if not isinstance(arg_name, str):
            raise TypeError(
                f"Model xacro args file '{resolved_model_xacro_args_file}' contains a non-string key "
                f'{arg_name!r} of type {type(arg_name).__name__}.'
            )
        if arg_name in ('namespace', 'robot_name', 'sim_file', 'ros2_control_config_file'):
            raise ValueError(
                f"Model xacro args file '{resolved_model_xacro_args_file}' sets launch-provided xacro argument "
                f"'{arg_name}'. Launch-provided xacro arguments are passed directly by the launch files and must not "
                'be set in model_xacro_args_file.'
            )

    return model_xacro_args


def _quote_xarg_value_if_needed(raw_value: str) -> str:
    """
    Quote xarg values containing whitespace so xacro parses them as one token.
    """
    return f'"{raw_value}"' if any(ch.isspace() for ch in raw_value) else raw_value
