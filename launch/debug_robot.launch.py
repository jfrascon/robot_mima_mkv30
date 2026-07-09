import ros2_launch_helpers as rlh
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetLaunchConfiguration,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.some_substitutions_type import SomeSubstitutionsType
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

    This launch file is a package-local debug tool. It starts a simple Gazebo world, includes the
    normal robot launch file, spawns the robot in Gazebo, and optionally starts RViz and the Gazebo
    GUI.
    """
    return LaunchDescription(
        [
            # Fixed launch configuration values for this debug launch.
            SetLaunchConfiguration('use_sim_time', 'True'),
            SetLaunchConfiguration('world_name', 'debug_world'),
            SetLaunchConfiguration('namespace', '/sim_debug'),
            # From here on, launch arguments to debug the robot.
            # Required.
            DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model variant.'),
            DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description="Robot's name."),
            # Required.
            DeclareLaunchArgument('params_file', description='Path to the complete robot parameters file.'),
            # Required.
            # When params_file_allow_substs is true, the caller must provide every extra key-value
            # pair referenced by the selected params_file as `$(var key)`.
            # This launch file provides the robot-specific keys it knows how to derive.
            # External keys that belong to a specific params file must be passed by the caller.
            DeclareLaunchArgument(
                'params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in params_file before including child launch files.',
            ),
            # Required.
            DeclareLaunchArgument(
                'model_xacro_args_file',
                description='Path to the YAML file with xacro arguments loaded from configuration.',
            ),
            # Required.
            DeclareLaunchArgument('sim_file', description='Path to the simulation YAML file.'),
            # Required.
            DeclareLaunchArgument(
                'ros_gz_bridge_config_file', description='Path with the configuration for the bridge'
            ),
            DeclareLaunchArgument(
                'robot_state_publisher_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'ros_gz_bridge_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'controller_manager_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'joint_state_broadcaster_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the joint_state_broadcaster controller',
            ),
            DeclareLaunchArgument(
                'mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the mima_controller controller',
            ),
            DeclareLaunchArgument(
                'fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for the fork_trajectory_controller controller',
            ),
            DeclareLaunchArgument(
                'joint_state_broadcaster_controller_remappings',
                default_value=DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for joint_state_broadcaster',
            ),
            DeclareLaunchArgument(
                'mima_controller_remappings',
                default_value=DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for mima_controller',
            ),
            DeclareLaunchArgument(
                'fork_trajectory_controller_remappings',
                default_value=DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
                description='Remapping overrides for fork_trajectory_controller',
            ),
            DeclareLaunchArgument(
                'use_rviz',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Launch RViz2 if true.',
            ),
            DeclareLaunchArgument(
                'use_gz_gui',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Launch Gazebo Sim GUI client. If false, Gazebo Sim runs in headless mode.',
            ),
            _spawn_world(),
            _include_robot(),
            OpaqueFunction(function=_spawn_model),
            _launch_rviz(),
        ]
    )


def _include_robot() -> GroupAction:
    """
    Include the public robot launch with the fixed debug namespace and simulation clock.

    This debug launch declares the same robot-loading arguments as `robot.launch.py` and forwards
    them into the included launch file. That keeps the debug entry point explicit while still
    allowing callers to override RSP, bridge, ros2_control, spawner, and controller remapping
    options from this top-level launch file. The defaults are repeated here intentionally so this
    launch file can be used to test those public launch arguments directly.
    """
    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_model': LaunchConfiguration('robot_model'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': LaunchConfiguration('params_file_allow_substs'),
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'model_xacro_args_file': LaunchConfiguration('model_xacro_args_file'),
        'sim_file': LaunchConfiguration('sim_file'),
        'ros_gz_bridge_config_file': LaunchConfiguration('ros_gz_bridge_config_file'),
        'robot_state_publisher_node_args': LaunchConfiguration('robot_state_publisher_node_args'),
        'ros_gz_bridge_node_args': LaunchConfiguration('ros_gz_bridge_node_args'),
        'controller_manager_node_args': LaunchConfiguration('controller_manager_node_args'),
        'joint_state_broadcaster_spawner_options': LaunchConfiguration('joint_state_broadcaster_spawner_options'),
        'mima_controller_spawner_options': LaunchConfiguration('mima_controller_spawner_options'),
        'fork_trajectory_controller_spawner_options': LaunchConfiguration('fork_trajectory_controller_spawner_options'),
        'joint_state_broadcaster_controller_remappings': LaunchConfiguration(
            'joint_state_broadcaster_controller_remappings'
        ),
        'mima_controller_remappings': LaunchConfiguration('mima_controller_remappings'),
        'fork_trajectory_controller_remappings': LaunchConfiguration('fork_trajectory_controller_remappings'),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_mappings,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', 'robot.launch.py'])
                ),
                launch_arguments=launch_mappings.items(),
            )
        ],
    )


def _launch_rviz() -> Node:
    """Launch RViz with the package-local debug configuration when `use_rviz` is true."""
    return Node(
        package='rviz2',
        executable='rviz2',
        namespace=LaunchConfiguration('namespace'),
        arguments=['-d', PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'rviz', 'sim_debug.rviz'])],
        output='both',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )


def _spawn_model(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """Insert the robot model into the debug Gazebo world."""
    namespace = LaunchConfiguration('namespace').perform(ctx)
    robot_name = LaunchConfiguration('robot_name').perform(ctx)
    robot_namespace = rlh.compute_robot_namespace(namespace, robot_name)
    # Ensure the robot_description topic is fully qualified.
    robot_description_topic = rlh.resolve_name('/', rlh.resolve_name(robot_namespace, 'robot_description'))
    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'world_name': LaunchConfiguration('world_name'),
        'topic': robot_description_topic,
        'entity_name': robot_name,
        'allow_renaming': 'False',
        'x': '0.0',
        'y': '0.0',
        'z': '0.0',
        'R': '0.0',
        'P': '0.0',
        'Y': '0.0',
        'node_output': 'screen',
    }

    return [
        GroupAction(
            scoped=True,
            forwarding=False,
            launch_configurations=launch_mappings,
            actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        PathJoinSubstitution([FindPackageShare('ros_gz_tools'), 'launch', 'spawn_model.launch.py'])
                    ),
                    launch_arguments=launch_mappings.items(),
                )
            ],
        )
    ]


def _spawn_world() -> LaunchDescriptionEntity:
    """Start the debug Gazebo world through ros_gz_tools."""
    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'use_composition': 'False',
        'world_sdf_file': PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'worlds', 'debug_world.sdf']),
        'initial_sim_time': '0.0',
        'verbosity_level': '4',
        'use_gz_gui': LaunchConfiguration('use_gz_gui'),
        'gz_gui_config_file': '',
        'world_bridge_file': PathJoinSubstitution(
            [FindPackageShare('robot_mima_mkv30'), 'worlds', 'debug_world_bridge.yaml']
        ),
        'bridge_name': 'world_ros_gz_bridge',
        'bridge_subscription_heartbeat': '1000',
        'bridge_expand_gz_topic_names': 'True',
        'bridge_override_timestamps_with_wall_time': 'False',
        'bridge_override_frame_id': '',
        'bridge_use_respawn': 'False',
        'bridge_log_level': 'info',
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_mappings,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('ros_gz_tools'), 'launch', 'spawn_world.launch.py'])
                ),
                launch_arguments=launch_mappings.items(),
            )
        ],
    )
