import os
from pathlib import Path
from typing import Any, List, Tuple

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetLaunchConfiguration
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
    the model-specific `params_file`. If this launch file is called directly and
    `params_file` is empty, robot_state_publisher is launched without loading an
    external params file.
    """
    ldes: List[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
        DeclareLaunchArgument(
            'robot_model', default_value='base', choices=model_utils.get_models(), description='Robot model to publish'
        ),
        DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description='The unique name for the robot'),
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
        DeclareLaunchArgument('params_file', default_value='', description='Path to params file'),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='False',
            choices=['True', 'true', 'False', 'false'],
            description='Use simulation clock if true',
        ),
        DeclareLaunchArgument(
            'publish_frequency',
            default_value='',
            description='Frequency at which robot_state_publisher publishes TF transforms.',
        ),
        DeclareLaunchArgument(
            'ignore_timestamp',
            default_value='',
            choices=['True', 'true', 'False', 'false', ''],
            description='If True, robot_state_publisher accepts joint_state messages regardless of timestamp.',
        ),
        DeclareLaunchArgument(
            'use_robot_description_topic',
            default_value='',
            choices=['True', 'true', 'False', 'false', ''],
            description='If set, override whether robot_state_publisher uses robot_description as a topic.',
        ),
        # Force the frame prefix to empty string, since the robot_prefix is managed explicitly in this package with
        # robot_prefix.
        SetLaunchConfiguration('frame_prefix', ''),
        OpaqueFunction(function=_declare_model_launch_arguments),
        DeclareLaunchArgument('node_name', default_value='robot_state_publisher', description='Node name'),
        DeclareLaunchArgument('node_remappings_map', default_value='{}', description=rlh.REMAPPINGS_DESC),
        DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
        DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
        OpaqueFunction(function=_launch_rsp),
    ]

    return LaunchDescription(ldes)


def _build_xacro_command(ctx: LaunchContext) -> Tuple[List[Any], List[str]]:
    """
    Build the xacro command list and collect diagnostics for the selected model.
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

    cmd: List[Any] = [
        FindExecutable(name='xacro'),
        ' ',
        xacro_file,
        ' use_sim_mode:=',
        use_sim_time_lc,
        ' namespace:=',
        LaunchConfiguration('namespace'),
        ' robot_name:=',
        LaunchConfiguration('robot_name'),
    ]

    msgs: List[str] = []

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

    return cmd, msgs


def _declare_model_launch_arguments(ctx: LaunchContext) -> List[LaunchDescriptionEntity]:
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


def _launch_rsp(ctx: LaunchContext) -> List[LaunchDescriptionEntity]:
    """
    Launch robot_state_publisher for the selected model.
    """
    ldes: List[LaunchDescriptionEntity] = []
    cmd, msgs = _build_xacro_command(ctx)
    ldes.extend(rlh.to_log_info_actions(msgs))

    parameters: List[Any] = []
    params_file = LaunchConfiguration('params_file').perform(ctx)
    publish_frequency = LaunchConfiguration('publish_frequency').perform(ctx)
    ignore_timestamp = LaunchConfiguration('ignore_timestamp').perform(ctx)
    use_robot_description_topic = LaunchConfiguration('use_robot_description_topic').perform(ctx)
    frame_prefix = LaunchConfiguration('frame_prefix').perform(ctx)

    if params_file:
        if not Path(params_file).is_file():
            raise FileNotFoundError(f"Params file '{params_file}' does not exist.")

        parameters.append(ParameterFile(params_file, allow_substs=True))

    if publish_frequency:
        parameters.append({'publish_frequency': float(publish_frequency)})

    if ignore_timestamp:
        parameters.append({'ignore_timestamp': ignore_timestamp.lower() == 'true'})

    if use_robot_description_topic:
        parameters.append({'use_robot_description_topic': use_robot_description_topic.lower() == 'true'})

    if frame_prefix:
        parameters.append({'frame_prefix': frame_prefix})

    parameters.append(
        {
            'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool),
            'robot_description': ParameterValue(Command(cmd), value_type=str),
        }
    )

    node_name = LaunchConfiguration('node_name').perform(ctx)

    if not rlh.is_valid_name(node_name):
        raise RuntimeError(f"The name of the node must be ASCII [A-Za-z0-9_] only: '{node_name}'")

    node_options, node_remappings, node_ros_arguments = rlh.resolve_node_launch_configs(
        [node_name],
        LaunchConfiguration('node_options_map').perform(ctx),
        LaunchConfiguration('node_logging_options_map').perform(ctx),
        LaunchConfiguration('node_remappings_map').perform(ctx),
    )

    ldes.append(
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
    )

    return ldes


def _quote_xarg_value_if_needed(raw_value: str) -> str:
    """
    Quote xarg values containing whitespace so xacro parses them as one token.
    """
    return f'"{raw_value}"' if any(ch.isspace() for ch in raw_value) else raw_value
