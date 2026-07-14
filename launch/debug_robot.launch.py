import ros2_launch_helpers as rlh
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from robot_mima_mkv30.model_utils import (
    DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
    DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
    DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
    get_models,
)


def generate_launch_description() -> LaunchDescription:
    """
    Build the simulation debug launch description for one MiMA MKV30 robot model.

    This launch file is a package-local debug tool. It starts a simple Gazebo world, starts
    robot_state_publisher, spawns the robot in Gazebo, starts the robot bridge and controller
    spawners, and optionally starts RViz and the Gazebo GUI.
    """
    return LaunchDescription(
        [
            # Fixed launch configuration values for this debug launch.
            SetLaunchConfiguration('use_sim_time', 'True'),
            SetLaunchConfiguration('world_name', 'debug_world'),
            SetLaunchConfiguration('namespace', '/sim_debug'),
            # Launch arguments used to configure the robot.
            # Required.
            DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model variant.'),
            DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description="Robot's name."),
            # Required.
            DeclareLaunchArgument('robot_params_file', description='Path to the complete robot parameters file.'),
            # Required.
            DeclareLaunchArgument(
                'robot_params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in robot_params_file before including child launch files.',
            ),
            # Required.
            DeclareLaunchArgument(
                'robot_xacro_args_file',
                description='Path to the YAML file with xacro arguments loaded from configuration.',
            ),
            # Required.
            DeclareLaunchArgument('robot_sim_file', description='Path to the simulation YAML file.'),
            # Required.
            DeclareLaunchArgument(
                'robot_bridge_config_file', description='Path to the robot bridge configuration file.'
            ),
            DeclareLaunchArgument(
                'robot_rsp_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'robot_bridge_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'robot_controller_manager_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'robot_joint_state_broadcaster_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the joint_state_broadcaster controller',
            ),
            DeclareLaunchArgument(
                'robot_mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the mima_controller controller',
            ),
            DeclareLaunchArgument(
                'robot_fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the fork_trajectory_controller controller',
            ),
            DeclareLaunchArgument(
                'robot_joint_state_broadcaster_controller_remappings',
                default_value=DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for joint_state_broadcaster',
            ),
            DeclareLaunchArgument(
                'robot_mima_controller_remappings',
                default_value=DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for mima_controller',
            ),
            DeclareLaunchArgument(
                'robot_fork_trajectory_controller_remappings',
                default_value=DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for fork_trajectory_controller',
            ),
            DeclareLaunchArgument(
                'rviz_enabled',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Launch RViz2 if true.',
            ),
            DeclareLaunchArgument(
                'gzgui_enabled',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Launch Gazebo Sim GUI client. If false, Gazebo Sim runs in headless mode.',
            ),
            _include_spawn_world(),
            _include_robot_state_publisher(),
            OpaqueFunction(function=_include_spawn_model),
            _include_bridge(),
            _include_ros2_control(),
            _launch_rviz(),
        ]
    )


def _include_bridge() -> IncludeLaunchDescription:
    """Include the robot bridge after the model has been spawned in Gazebo."""

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_bridge.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'robot_name': LaunchConfiguration('robot_name'),
            'robot_bridge_params_file': LaunchConfiguration('robot_params_file'),
            'robot_bridge_params_file_allow_substs': LaunchConfiguration('robot_params_file_allow_substs'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'robot_bridge_config_file': LaunchConfiguration('robot_bridge_config_file'),
            'robot_bridge_node_args': LaunchConfiguration('robot_bridge_node_args'),
        }.items(),
    )


def _include_robot_state_publisher() -> IncludeLaunchDescription:
    """Include robot_state_publisher before spawning the robot model in Gazebo."""

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_robot_state_publisher.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'robot_model': LaunchConfiguration('robot_model'),
            'robot_name': LaunchConfiguration('robot_name'),
            'robot_rsp_params_file': LaunchConfiguration('robot_params_file'),
            'robot_rsp_params_file_allow_substs': LaunchConfiguration('robot_params_file_allow_substs'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'robot_xacro_args_file': LaunchConfiguration('robot_xacro_args_file'),
            'robot_sim_file': LaunchConfiguration('robot_sim_file'),
            'robot_rsp_node_args': LaunchConfiguration('robot_rsp_node_args'),
        }.items(),
    )


def _include_ros2_control() -> IncludeLaunchDescription:
    """Include controller spawners after Gazebo has loaded the ros2_control plugin."""

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'robot_name': LaunchConfiguration('robot_name'),
            'robot_ros2_control_params_file': LaunchConfiguration('robot_params_file'),
            'robot_ros2_control_params_file_allow_substs': LaunchConfiguration('robot_params_file_allow_substs'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
            'start_robot_controller_manager': 'False',
            'robot_controller_manager_node_args': LaunchConfiguration('robot_controller_manager_node_args'),
            'robot_joint_state_broadcaster_spawner_options': LaunchConfiguration(
                'robot_joint_state_broadcaster_spawner_options'
            ),
            'robot_mima_controller_spawner_options': LaunchConfiguration('robot_mima_controller_spawner_options'),
            'robot_fork_trajectory_controller_spawner_options': LaunchConfiguration(
                'robot_fork_trajectory_controller_spawner_options'
            ),
            'robot_joint_state_broadcaster_controller_remappings': LaunchConfiguration(
                'robot_joint_state_broadcaster_controller_remappings'
            ),
            'robot_mima_controller_remappings': LaunchConfiguration('robot_mima_controller_remappings'),
            'robot_fork_trajectory_controller_remappings': LaunchConfiguration(
                'robot_fork_trajectory_controller_remappings'
            ),
        }.items(),
    )


def _launch_rviz() -> Node:
    """Launch RViz with the package-local debug configuration when `rviz_enabled` is true."""
    return Node(
        package='rviz2',
        executable='rviz2',
        namespace=LaunchConfiguration('namespace'),
        arguments=['-d', PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'rviz', 'sim_debug.rviz'])],
        output='both',
        condition=IfCondition(LaunchConfiguration('rviz_enabled')),
    )


def _include_spawn_model(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """Insert the robot model into the debug Gazebo world."""
    namespace = LaunchConfiguration('namespace').perform(ctx)
    robot_name = LaunchConfiguration('robot_name').perform(ctx)
    robot_namespace = rlh.compute_robot_namespace(namespace, robot_name)
    # Ensure the robot_description topic is fully qualified.
    robot_description_topic = rlh.resolve_name('/', rlh.resolve_name(robot_namespace, 'robot_description'))

    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([FindPackageShare('ros_gz_tools'), 'launch', 'spawn_model.launch.py'])
            ),
            launch_arguments={
                'world_name': LaunchConfiguration('world_name'),
                'model_sdf_file': '',
                'model_sdf_string': '',
                'model_sdf_topic': robot_description_topic,
                'model_entity_name': robot_name,
                'model_allow_renaming': 'False',
                'model_pose_x': '0.0',
                'model_pose_y': '0.0',
                'model_pose_z': '0.0',
                'model_pose_roll': '0.0',
                'model_pose_pitch': '0.0',
                'model_pose_yaw': '0.0',
                'model_spawn_node_output': 'screen',
                'model_spawn_node_log_level': 'info',
            }.items(),
        )
    ]


def _include_spawn_world() -> IncludeLaunchDescription:
    """Include the debug world launch with the arguments expected by ros_gz_tools."""

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('ros_gz_tools'), 'launch', 'spawn_world.launch.py'])
        ),
        launch_arguments={
            'namespace': LaunchConfiguration('namespace'),
            'gzserver_use_composition': 'False',
            'gzserver_create_own_container': 'False',
            'gzserver_container_name': '',
            'gzserver_initial_sim_time': '0.0',
            'gzserver_verbosity_level': '4',
            'gzgui_enabled': LaunchConfiguration('gzgui_enabled'),
            'gzgui_config_file': '',
            'world_sdf_file': PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'worlds', 'debug_world.sdf']),
            'world_sdf_string': '',
            'world_bridge_config_file': PathJoinSubstitution(
                [FindPackageShare('robot_mima_mkv30'), 'worlds', 'debug_world_bridge.yaml']
            ),
            'world_bridge_name': 'world_bridge',
            'world_bridge_subscription_heartbeat': '1000',
            'world_bridge_expand_gz_topic_names': 'True',
            'world_bridge_override_timestamps_with_wall_time': 'False',
            'world_bridge_override_frame_id': '',
            'world_bridge_use_respawn': 'False',
            'world_bridge_log_level': 'info',
        }.items(),
    )
