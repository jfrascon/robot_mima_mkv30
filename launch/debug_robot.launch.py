import sys
from pathlib import Path

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    OpaqueFunction,
    RegisterEventHandler,
    SetLaunchConfiguration,
)
from launch.conditions import IfCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.some_substitutions_type import SomeSubstitutionsType
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ros_gz_sim.actions import GzServer

from robot_mima_mkv30.model_utils import get_models


def generate_launch_description() -> LaunchDescription:
    """
    Build the simulation debug launch description for one MiMA MKV30 robot model.

    This launch file is a package-local debug tool. It starts a simple Gazebo world, includes the
    normal robot launch file, waits until `robot_description` exists, spawns the robot in Gazebo,
    and optionally starts RViz and the Gazebo GUI.
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
            DeclareLaunchArgument(
                'rsp_node_arguments', default_value='{}', description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC
            ),
            DeclareLaunchArgument(
                'bridge_node_arguments', default_value='{}', description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC
            ),
            DeclareLaunchArgument(
                'controller_manager_node_arguments', default_value='{}', description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC
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
                default_value='[["joint_states","joint_states"]]',
                description='Remapping overrides for the joint_state_broadcaster controller',
            ),
            DeclareLaunchArgument(
                'mima_controller_remappings',
                default_value=(
                    '[["~/reference","cmd_vel"],["~/odometry","odom"],["~/tf_odometry","/tf"],'
                    '["~/controller_state","steering_controller_status"]]'
                ),
                description='Remapping overrides for the mima_controller controller',
            ),
            DeclareLaunchArgument(
                'fork_trajectory_controller_remappings',
                default_value=(
                    '[["~/joint_trajectory","fork_trajectory"],'
                    '["~/follow_joint_trajectory","fork_follow_joint_trajectory"],'
                    '["~/controller_state","fork_trajectory_state"]]'
                ),
                description='Remapping overrides for the fork_trajectory_controller controller',
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
            _launch_gazebo_server(),
            _launch_clock_bridge(),
            _include_robot(),
            OpaqueFunction(function=_spawn_robot),
            _launch_gazebo_gui(),
            _launch_rviz(),
        ]
    )


def _include_robot() -> GroupAction:
    """
    Include the public robot launch with the fixed debug namespace and simulation clock.

    This debug launch keeps only the arguments that are useful for selecting and loading the robot.
    The normal defaults from `robot.launch.py` are used for RSP, bridge, ros2_control, spawners,
    and controller remappings.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_model': LaunchConfiguration('robot_model'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': LaunchConfiguration('params_file_allow_substs'),
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'model_xacro_args_file': LaunchConfiguration('model_xacro_args_file'),
        'sim_file': LaunchConfiguration('sim_file'),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', 'robot.launch.py'])
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )


def _launch_clock_bridge() -> Node:
    """
    Bridge Gazebo clock to ROS `/clock`.

    This launch file always runs the robot with `use_sim_time=True`. ROS nodes that use simulated
    time need `/clock`, so the debug world provides this bridge directly.
    """
    return Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='debug_world_clock_bridge',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
        output='screen',
    )


def _launch_gazebo_gui() -> ExecuteProcess:
    """Launch the Gazebo GUI client only when `use_gz_gui` is true."""
    return ExecuteProcess(
        cmd=['gz', 'sim', '-g'], output='screen', condition=IfCondition(LaunchConfiguration('use_gz_gui'))
    )


def _launch_gazebo_server() -> GzServer:
    """Launch the Gazebo server with the package-local debug world."""
    return GzServer(
        world_sdf_file=PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'worlds', 'debug_world.sdf']),
        world_sdf_string='',
        container_name='',
        create_own_container=False,
        use_composition=False,
        initial_sim_time=0.0,
    )


def _launch_rviz() -> Node:
    """Launch RViz with the package-local debug configuration when `use_rviz` is true."""
    return Node(
        package='rviz2',
        executable='rviz2',
        namespace=LaunchConfiguration('namespace'),
        arguments=['-d', PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'rviz', 'sim_debug.rviz'])],
        output='screen',
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )


def _spawn_robot(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Wait for `robot_description` and then insert the robot into the debug Gazebo world.

    The robot launch starts robot_state_publisher. This function waits until the description topic
    is visible in the ROS graph before running `ros_gz_sim create`, because Gazebo reads the model
    XML from that topic.
    """
    robot_name = LaunchConfiguration('robot_name').perform(ctx)
    namespace = LaunchConfiguration('namespace').perform(ctx)
    robot_namespace = rlh.compute_robot_namespace(namespace, robot_name)
    # Safety measure: Always ensure the robot description topic is fully qualified, i.e., starts with a leading slash.
    robot_description_topic = f'/{rlh.resolve_name(robot_namespace, "robot_description").lstrip("/")}'
    wait_script = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('scripts', 'wait_for_ros_topic.py')

    if not wait_script.is_file():
        raise FileNotFoundError(f"Required wait script '{wait_script}' does not exist.")

    wait_for_robot_description = ExecuteProcess(
        cmd=[sys.executable, str(wait_script), robot_description_topic, '--timeout', '60.0'], output='screen'
    )

    spawn_robot = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-world',
            LaunchConfiguration('world_name'),
            '-topic',
            robot_description_topic,
            '-name',
            robot_name,
            '-allow_renaming',
            'false',
            '-x',
            '0.0',
            '-y',
            '0.0',
            '-z',
            '0.0',
            '-R',
            '0.0',
            '-P',
            '0.0',
            '-Y',
            '0.0',
        ],
        output='screen',
    )

    return [
        LogInfo(msg=f"Waiting for '{robot_description_topic}' before spawning '{robot_name}'"),
        wait_for_robot_description,
        RegisterEventHandler(
            OnProcessExit(
                target_action=wait_for_robot_description,
                on_exit=[
                    LogInfo(
                        msg=[
                            f"Spawning robot '{robot_name}' into Gazebo world '",
                            LaunchConfiguration('world_name'),
                            "'",
                        ]
                    ),
                    spawn_robot,
                ],
            )
        ),
    ]
