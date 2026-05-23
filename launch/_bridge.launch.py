from pathlib import Path
from typing import Any, List

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

    This launch file is meant to be included by `model_*.launch.py`, not to be
    used as the user entry point for the `robot_mima_mkv30` package.

    The model wrapper is responsible for passing a model-specific `bridge_file`
    and `params_file` when those files should be loaded. If this launch file is
    called directly and one of those arguments is left empty, the corresponding
    external file is not loaded.
    """
    ldes: List[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('project_namespace', default_value='', description='Project namespace'),
        DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description='The unique name for the robot'),
        OpaqueFunction(
            function=rlh.set_robot_namespace,
            kwargs={
                'namespace_key': 'project_namespace',
                'robot_name_key': 'robot_name',
                'robot_namespace_key': 'namespace',
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
            'config_file', default_value='', description='YAML file to be loaded as the bridge configuration'
        ),
        DeclareLaunchArgument(
            'subscription_heartbeat',
            default_value='',
            description='Period (ms) at which the node checks for new subscribers for lazy '
            'bridges. Good default value is 1000',
        ),
        DeclareLaunchArgument(
            'expand_gz_topic_names',
            default_value='',
            choices=['True', 'true', 'False', 'false', ''],
            description='Enable or disable ROS namespace applied on GZ topics',
        ),
        DeclareLaunchArgument(
            'override_timestamps_with_wall_time',
            default_value='',
            choices=['True', 'true', 'False', 'false', ''],
            description='Override the header.stamp field of outgoing messages with wall time (GZ to ROS).',
        ),
        DeclareLaunchArgument(
            'override_frame_id',
            default_value='',
            description='Override the header.frame_id field with a new string value (GZ to ROS)',
        ),
        DeclareLaunchArgument('node_name', default_value='bridge', description='Node name'),
        DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
        DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
        OpaqueFunction(function=_launch_bridge),
    ]

    return LaunchDescription(ldes)


def _launch_bridge(ctx: LaunchContext) -> List[LaunchDescriptionEntity]:
    """
    Launch the ROS-GZ bridge for one robot instance.
    """
    # The parameter `use_sim_time` is managed in the launch file.
    # If the field `use_sim_time` appears in the params_file, it is ignored.
    # Bridges are only launch in simulation, so if `use_sim_time` is false, do not launch the bridge
    # and return an empty list of launch entities.
    use_sim_time = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('use_sim_time'), bool), bool
    )

    if not use_sim_time:
        return []

    # If the params_file exists, load it as a ParameterFile.
    # If any parameter is also provided to this launch file, it takes precedence over the
    # params_file.
    # This allows to override specific parameters in the params_file without having to create a new
    # params file.

    parameters: List[Any] = []

    params_file = LaunchConfiguration('params_file').perform(ctx)
    subscription_heartbeat = LaunchConfiguration('subscription_heartbeat').perform(ctx)
    config_file = LaunchConfiguration('config_file').perform(ctx)
    expand_gz_topic_names = LaunchConfiguration('expand_gz_topic_names').perform(ctx)
    override_timestamps_with_wall_time = LaunchConfiguration('override_timestamps_with_wall_time').perform(ctx)
    override_frame_id = LaunchConfiguration('override_frame_id').perform(ctx)

    if params_file:
        if not Path(params_file).is_file():
            raise FileNotFoundError(f"Params file '{params_file}' not found.")

        parameters.append(ParameterFile(params_file, allow_substs=True))

    if subscription_heartbeat:
        try:
            parameters.append({'subscription_heartbeat': int(subscription_heartbeat)})
        except ValueError as exc:
            raise ValueError(
                f"Invalid value for subscription_heartbeat: '{subscription_heartbeat}'. Must be an integer."
            ) from exc

    if config_file:
        if not Path(config_file).is_file():
            raise FileNotFoundError(f"Bridge file '{config_file}' not found.")

        parameters.append({'config_file': config_file})

    if expand_gz_topic_names:
        parameters.append({'expand_gz_topic_names': expand_gz_topic_names.lower() == 'true'})

    if override_timestamps_with_wall_time:
        parameters.append({'override_timestamps_with_wall_time': override_timestamps_with_wall_time.lower() == 'true'})

    if override_frame_id:
        parameters.append({'override_frame_id': override_frame_id})

    parameters.append({'use_sim_time': use_sim_time})

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
            namespace=LaunchConfiguration('namespace'),
            parameters=parameters,
            ros_arguments=node_ros_arguments[node_name],
            output=node_options[node_name]['output'],
            emulate_tty=node_options[node_name]['emulate_tty'],
            respawn=node_options[node_name]['respawn'],
            respawn_delay=node_options[node_name]['respawn_delay'],
        )
    ]
