from pathlib import Path
from typing import Any

import ros2_launch_helpers as rlh
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile

from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal Gazebo bridge launch description for one robot model wrapper.

    This launch file is meant to be included by `model_*.launch.py`, but can
    be run directly as well. When params_file_allow_substs is true, the caller
    can pass the launch keys used by the parameter file as extra CLI arguments
    even if this launch file does not declare those keys.

    When use_sim_time is false, this launch file returns no bridge node because
    the ROS-GZ bridge is only used in simulation.
    """
    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
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
        DeclareLaunchArgument('node_name', default_value='bridge', description='Node name'),
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
        OpaqueFunction(function=_launch_node),
    ]

    return LaunchDescription(ldes)


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch the ROS-GZ bridge for one robot instance.

    The bridge is only useful when Gazebo is running, so this function returns no
    launch entities when `use_sim_time` is false. In simulation it resolves the
    prepared params file, applies node options, and starts `ros_gz_bridge`.
    """

    # Bridges are only launched in simulation, so if `use_sim_time` is false, do
    # not launch the bridge and return an empty list of launch entities.
    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    if not use_sim_time:
        return []

    params_file = rlh.resolve_file(LaunchConfiguration('params_file').perform(ctx))

    if not Path(params_file).is_file():
        raise FileNotFoundError(f"Params file '{params_file}' does not exist.")

    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    # When params_file_allow_substs is true, the caller must provide every launch
    # context key used by the parameter file. If it is false, the file is loaded
    # without expanding launch substitutions.
    parameters: list[Any] = [
        ParameterFile(params_file, allow_substs=params_file_allow_substs),
        # `expand_gz_topic_names` is always true because Gazebo topics are
        # expected to include the robot namespace so multiple robots can run in
        # the same simulation.
        # `override_frame_id` is set to an empty string because Gazebo plugins
        # publish the required frame_id.
        {'use_sim_time': use_sim_time, 'expand_gz_topic_names': True, 'override_frame_id': ''},
    ]

    node_name = LaunchConfiguration('node_name').perform(ctx)

    if not rlh.is_valid_name(node_name):
        raise RuntimeError(f"The name of the node must be ASCII [A-Za-z0-9_] only: '{node_name}'")

    node_options, _, node_ros_arguments = rlh.resolve_node_launch_configs(
        [node_name],
        LaunchConfiguration('node_options_map').perform(ctx),
        LaunchConfiguration('node_logging_options_map').perform(ctx),
        '{}',
    )

    return [
        Node(
            package='ros_gz_bridge',
            executable='bridge_node',
            name=node_name,
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=parameters,
            ros_arguments=node_ros_arguments[node_name],
            output=node_options[node_name]['output'],
            emulate_tty=node_options[node_name]['emulate_tty'],
            respawn=node_options[node_name]['respawn'],
            respawn_delay=node_options[node_name]['respawn_delay'],
        )
    ]
