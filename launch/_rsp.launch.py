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
from robot_mima_mkv30 import model_utils


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
        DeclareLaunchArgument('robot_model', choices=model_utils.get_models(), description='Robot model to publish'),
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
        DeclareLaunchArgument('node_name', default_value='robot_state_publisher', description='Node name'),
        DeclareLaunchArgument('node_remappings_map', default_value='{}', description=rlh.REMAPPINGS_DESC),
        DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
        DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
        OpaqueFunction(function=_declare_model_launch_arguments),
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
    Build the xacro command list for the selected model.
    """
    robot_model = LaunchConfiguration('robot_model').perform(ctx)

    # Get the xacro file for the selected model.
    xacro_file = os.path.join(
        get_package_share_directory('robot_mima_mkv30'), 'urdf', 'models', f'model_{robot_model}.xacro'
    )

    if not Path(xacro_file).is_file():
        raise FileNotFoundError(f"File '{xacro_file}' not found")

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    cmd: list[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        xacro_file,
        ' use_sim_mode:=',
        use_sim_time_lc,
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
        ' ros2_control_config_file:=',
        LaunchConfiguration('params_file'),
    ]

    # Configure the robot's xacro file by means of xacro:args passed as launch
    # context keys. Iterate over the xacro:arg names of the selected model and
    # get their values from the launch context.
    for xarg_name in model_utils.get_xarg_names(robot_model):
        value = LaunchConfiguration(xarg_name).perform(ctx)

        if xarg_name == 'sim_file':
            # `sim_file` is a xacro argument. When the application is running
            # without simulation time, the simulation file is not used.
            if not use_sim_time_bool:
                value = ''
            elif value:
                value = rlh.resolve_file(value)

        cmd.extend([' ', f'{xarg_name}:=', _quote_xarg_value_if_needed(value)])

    return cmd


def _declare_model_launch_arguments(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Declare the model launch arguments for the selected robot model.
    """
    robot_model = LaunchConfiguration('robot_model').perform(ctx)

    if not model_utils.model_exists(robot_model):
        raise ValueError(
            f"Model '{robot_model}' for 'robot_mima_mkv30' is not available. "
            f'Available robot models: {", ".join(model_utils.get_models())}'
        )

    return model_utils.declare_launch_arguments(robot_model)


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch robot_state_publisher for the selected model.
    """
    params_file = rlh.resolve_file(LaunchConfiguration('params_file').perform(ctx))

    if not params_file:
        raise RuntimeError('params_file must point to the robot_state_publisher YAML file.')

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


def _quote_xarg_value_if_needed(raw_value: str) -> str:
    """
    Quote xarg values containing whitespace so xacro parses them as one token.
    """
    return f'"{raw_value}"' if any(ch.isspace() for ch in raw_value) else raw_value
