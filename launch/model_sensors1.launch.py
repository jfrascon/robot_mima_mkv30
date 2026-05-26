import os

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from launch import LaunchDescription, LaunchDescriptionEntity
from robot_mima_mkv30 import model_utils

ROBOT_MODEL = 'sensors1'


def generate_launch_description() -> LaunchDescription:
    """
    Build the launch description for the MiMA MKV30 model with sensors.
    """
    ldes: list[LaunchDescriptionEntity] = [
        SetLaunchConfiguration('robot_type', 'mima_mkv30'),
        SetLaunchConfiguration('robot_model', ROBOT_MODEL),
        DeclareLaunchArgument('namespace', default_value='', description="Project's namespace"),
        DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description="Robot's name"),
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
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(
                get_package_share_directory('robot_mima_mkv30'), 'config', f'model_{ROBOT_MODEL}', 'example_params.yaml'
            ),
            description='Path to params file. If empty, robot_state_publisher starts without it.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='False',
            choices=['True', 'true', 'False', 'false'],
            description='Use simulation clock if true. This also enables Gazebo simulation blocks.',
        ),
        DeclareLaunchArgument(
            'bridge_file',
            default_value=os.path.join(
                get_package_share_directory('robot_mima_mkv30'), 'config', f'model_{ROBOT_MODEL}', 'example_bridge.yaml'
            ),
            description='Path to bridge file. If empty, the bridge node is not launched.',
        ),
    ]

    # Declare the launch arguments for the xacro:args of the selected model
    # These launch arguments configure the robot model when building the robot description with
    # the xacro command.
    # Please, be aware that 'sim_file' and 'controller_config_file' are declare via this function, because these files
    # are used in the xacro model via xacro arguments.
    ldes.extend(model_utils.declare_launch_arguments(ROBOT_MODEL))

    ldes.extend(
        [
            DeclareLaunchArgument(
                'rsp_publish_frequency',
                default_value='',
                description='Override robot_state_publisher publish_frequency.',
            ),
            DeclareLaunchArgument(
                'rsp_ignore_timestamp',
                default_value='',
                choices=['True', 'true', 'False', 'false', ''],
                description='Override whether robot_state_publisher ignores joint_state timestamps.',
            ),
            DeclareLaunchArgument(
                'rsp_use_robot_description_topic',
                default_value='',
                choices=['True', 'true', 'False', 'false', ''],
                description='Override whether robot_state_publisher uses robot_description as a topic.',
            ),
            DeclareLaunchArgument(
                'bridge_subscription_heartbeat', default_value='', description='Override bridge subscription_heartbeat.'
            ),
            DeclareLaunchArgument(
                'bridge_expand_gz_topic_names',
                default_value='',
                choices=['True', 'true', 'False', 'false', ''],
                description='Override whether the bridge expands Gazebo topic names.',
            ),
            DeclareLaunchArgument(
                'bridge_override_timestamps_with_wall_time',
                default_value='',
                choices=['True', 'true', 'False', 'false', ''],
                description='Override bridge timestamps with wall time.',
            ),
            DeclareLaunchArgument(
                'bridge_override_frame_id', default_value='', description='Override bridge outgoing frame_id.'
            ),
            DeclareLaunchArgument('rsp_node_name', default_value='robot_state_publisher', description='Node name'),
            DeclareLaunchArgument('bridge_node_name', default_value='bridge', description='Node name'),
            # Controllers have their own remappings argument, next.
            DeclareLaunchArgument('node_remappings_map', default_value='{}', description=rlh.REMAPPINGS_DESC),
            DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
            DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
            DeclareLaunchArgument(
                'controller_remappings',
                default_value='{}',
                description=(
                    'JSON object indexed by controller name. Entries override the default '
                    'remappings for the matching controller.'
                ),
            ),
            # Prepare controller_config_file for consumers that need a concrete YAML path.
            OpaqueFunction(function=model_utils.process_controller_config_file),
            _include_rsp(),
            _include_ros2_control(),
            _include_bridge(),
        ]
    )

    return LaunchDescription(ldes)


def _include_bridge() -> IncludeLaunchDescription:
    """
    Include the Gazebo bridge launch file for the sensors1 model.
    """
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_bridge.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'robot_name': LaunchConfiguration('robot_name'),
            'params_file': LaunchConfiguration('params_file'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'config_file': LaunchConfiguration('bridge_file'),
            'subscription_heartbeat': LaunchConfiguration('bridge_subscription_heartbeat'),
            'expand_gz_topic_names': LaunchConfiguration('bridge_expand_gz_topic_names'),
            'override_timestamps_with_wall_time': LaunchConfiguration('bridge_override_timestamps_with_wall_time'),
            'override_frame_id': LaunchConfiguration('bridge_override_frame_id'),
            'node_name': LaunchConfiguration('bridge_node_name'),
            'node_options_map': LaunchConfiguration('node_options_map'),
            'node_logging_options_map': LaunchConfiguration('node_logging_options_map'),
        }.items(),
    )


def _include_rsp() -> IncludeLaunchDescription:
    """
    Include robot_state_publisher for the sensors1 model.
    """
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_rsp.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'robot_model': LaunchConfiguration('robot_model'),
            'robot_name': LaunchConfiguration('robot_name'),
            'params_file': LaunchConfiguration('params_file'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'publish_frequency': LaunchConfiguration('rsp_publish_frequency'),
            'ignore_timestamp': LaunchConfiguration('rsp_ignore_timestamp'),
            'use_robot_description_topic': LaunchConfiguration('rsp_use_robot_description_topic'),
            'node_name': LaunchConfiguration('rsp_node_name'),
            'node_remappings_map': LaunchConfiguration('node_remappings_map'),
            'node_options_map': LaunchConfiguration('node_options_map'),
            'node_logging_options_map': LaunchConfiguration('node_logging_options_map'),
            **model_utils.get_launch_configuration_entries(ROBOT_MODEL),
        }.items(),
    )


def _include_ros2_control() -> IncludeLaunchDescription:
    """
    Include ros2_control preparation for the selected time mode.
    """
    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
        ),
        launch_arguments={
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            # The launch argument `controller_config_file` is  Declared via the function
            # `model_utils.declare_launch_arguments` based on the xacro arguments of the model.
            # In this model an input to the xacro file, used in simulation time, is also an input
            # to the ros2_control_node, when the model is launched in real time.
            'controller_config_file': LaunchConfiguration('controller_config_file'),
            'namespace': LaunchConfiguration('namespace'),
            'robot_name': LaunchConfiguration('robot_name'),
            'robot_model': LaunchConfiguration('robot_model'),
            'controller_remappings': LaunchConfiguration('controller_remappings'),
        }.items(),
    )
