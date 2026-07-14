from pathlib import Path
from tempfile import NamedTemporaryFile

import ros2_launch_helpers as rlh
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetLaunchConfiguration
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.substitutions import FindPackageShare
from robot_mima_mkv30.model_utils import (
    DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
    DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
    DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
    get_models,
)


def generate_launch_description() -> LaunchDescription:
    """
    Build the launch description for one MiMA MKV30 robot model.

    `use_sim_time` only controls the ROS clock used by the launched nodes.
    When it is false, nodes use wall time from the host system.
    When it is true, nodes read time from the `/clock` topic.

    `robot_sim_file` controls whether the xacro model loads simulation-specific elements, such as
    Gazebo plugins. Those plugins only make sense when the robot is launched for a simulated system
    that publishes `/clock`.

    Therefore, `use_sim_time=false` and a non-empty `robot_sim_file` is rejected.
    That combination would ask for simulation plugins while launching the robot in non-simulated
    time.

    When `use_sim_time=true`, `robot_sim_file` may be empty or non-empty.
    An empty value is valid for cases such as rosbag playback, where `/clock` exists but Gazebo
    plugins are not loaded by this launch file.
    A non-empty value loads the simulation-specific xacro elements and enables the bridge include.

    `start_robot_controller_manager` controls who starts the robot controller manager.
    When it is true, this launch file starts a local controller manager through ros2_control_node.
    When it is false, this launch file still starts the controller spawners, but those spawners
    expect an already running controller manager in the robot namespace.
    This is the usual setup when Gazebo loads the ros2_control plugin from `robot_sim_file`.
    """

    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model variant.'),
            DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description="Robot's name"),
            DeclareLaunchArgument(
                'robot_params_file',
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare('robot_mima_mkv30'),
                        'config',
                        ['model_', LaunchConfiguration('robot_model')],
                        'default_params.yaml',
                    ]
                ),
                description='Path to the complete robot parameters file.',
            ),
            DeclareLaunchArgument(
                'robot_params_file_allow_substs',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in robot_params_file before including child launch files.',
            ),
            DeclareLaunchArgument(
                'use_sim_time',
                default_value='False',
                choices=['True', 'true', 'False', 'false'],
                description='Use ROS time from /clock if true.',
            ),
            DeclareLaunchArgument(
                'robot_xacro_args_file',
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare('robot_mima_mkv30'),
                        'config',
                        ['model_', LaunchConfiguration('robot_model')],
                        'default_xacro_args.yaml',
                    ]
                ),
                description='Path to the YAML file with xacro arguments loaded from configuration.',
            ),
            DeclareLaunchArgument(
                'robot_sim_file',
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare('robot_mima_mkv30'),
                        'config',
                        ['model_', LaunchConfiguration('robot_model')],
                        'default_simulation.yaml',
                    ]
                ),
                description='Path to the simulation YAML file.',
            ),
            DeclareLaunchArgument(
                'robot_bridge_config_file',
                default_value=PathJoinSubstitution(
                    [
                        FindPackageShare('robot_mima_mkv30'),
                        'config',
                        ['model_', LaunchConfiguration('robot_model')],
                        'default_bridge.yaml',
                    ]
                ),
                description='Path to the robot bridge configuration file.',
            ),
            DeclareLaunchArgument(
                'start_robot_controller_manager',
                default_value='True',
                choices=['True', 'true', 'False', 'false'],
                description='Start the robot controller manager if true.',
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
                description='Options for the joint_state_broadcaster controller spawner',
            ),
            DeclareLaunchArgument(
                'robot_mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the mima_controller controller spawner',
            ),
            DeclareLaunchArgument(
                'robot_fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the fork_trajectory_controller controller spawner',
            ),
            DeclareLaunchArgument(
                'robot_joint_state_broadcaster_controller_remappings',
                default_value=DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
                description='Remappings for the joint_state_broadcaster controller',
            ),
            DeclareLaunchArgument(
                'robot_mima_controller_remappings',
                default_value=DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
                description='Remappings for the mima_controller controller',
            ),
            DeclareLaunchArgument(
                'robot_fork_trajectory_controller_remappings',
                default_value=DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
                description='Remappings for the fork_trajectory_controller controller',
            ),
            rlh.RequireFile(path=LaunchConfiguration('robot_params_file')),
            SetLaunchConfiguration('robot_type', 'mima_mkv30'),
            # Insert `robot_namespace` and `robot_prefix` into the launch context.
            # Their values can then be substituted in the parameter file if needed.
            rlh.SetRobotNamespace(
                namespace=LaunchConfiguration('namespace'),
                robot_name=LaunchConfiguration('robot_name'),
                output_context_key='robot_namespace',
            ),
            rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), output_context_key='robot_prefix'),
            OpaqueFunction(function=_include_child_launch_files),
        ]
    )


def _include_child_launch_files(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    ldes: list[LaunchDescriptionEntity] = []

    # Render the parameter YAML once if needed.
    # Each child action receives either the original path or the rendered parameters file.
    # Child actions do not need to render the parameter file again.

    params_file = LaunchConfiguration('robot_params_file').perform(ctx)

    if perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('robot_params_file_allow_substs'), bool), bool
    ):
        # Create a temporary file to hold the rendered parameters.
        with NamedTemporaryFile(prefix='params_', suffix='.yaml', delete=False) as temp_file:
            output_path = Path(temp_file.name)
        rlh.render_params_file(params_file, ctx, output_path)
        params_file = str(output_path)

    use_sim_time = (
        perform_typed_substitution(ctx, normalize_typed_substitution(LaunchConfiguration('use_sim_time'), bool), bool),
    )

    robot_sim_file = LaunchConfiguration('robot_sim_file').perform(ctx)

    # When topic '/clock' is not used as time source, it means the robot model is deployed in real
    # conditions. In this case, the simulation file must be empty because simulation plugins must
    # not be loaded.
    if not use_sim_time and robot_sim_file:
        raise ValueError('robot_sim_file must be empty when use_sim_time is false.')

    # When the robot_sim_file is provided, check that it exists.
    if robot_sim_file and not Path(robot_sim_file).is_file():
        raise FileNotFoundError(f"File '{robot_sim_file}' does not exist.")

    # Include robot_state_publisher.
    ldes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution(
                    [FindPackageShare('robot_mima_mkv30'), 'launch', '_robot_state_publisher.launch.py']
                )
            ),
            launch_arguments={
                'namespace': LaunchConfiguration('namespace'),
                'robot_model': LaunchConfiguration('robot_model'),
                'robot_name': LaunchConfiguration('robot_name'),
                'robot_rsp_params_file': params_file,
                'robot_rsp_params_file_allow_substs': 'False',  # Params file has already been rendered.
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'robot_xacro_args_file': LaunchConfiguration('robot_xacro_args_file'),
                'robot_sim_file': robot_sim_file,
                'robot_rsp_node_args': LaunchConfiguration('robot_rsp_node_args'),
            }.items(),
        )
    )

    # Include bridge only when a simulation file is provided.
    # Without simulation plugins, Gazebo does not publish robot plugin topics for the bridge.
    if robot_sim_file:
        ldes.append(
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_bridge.launch.py'])
                ),
                launch_arguments={
                    'namespace': LaunchConfiguration('namespace'),
                    'robot_name': LaunchConfiguration('robot_name'),
                    'robot_bridge_params_file': params_file,
                    'robot_bridge_params_file_allow_substs': 'False',  # Params file has already been rendered.
                    'use_sim_time': LaunchConfiguration('use_sim_time'),
                    'robot_bridge_config_file': LaunchConfiguration('robot_bridge_config_file'),
                    'robot_bridge_node_args': LaunchConfiguration('robot_bridge_node_args'),
                }.items(),
            )
        )

    # Include ros2_control.
    ldes.append(
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
            ),
            launch_arguments={
                'namespace': LaunchConfiguration('namespace'),
                'robot_name': LaunchConfiguration('robot_name'),
                'robot_ros2_control_params_file': params_file,
                'robot_ros2_control_params_file_allow_substs': 'False',  # Params file has already been rendered.
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'start_robot_controller_manager': LaunchConfiguration('start_robot_controller_manager'),
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
    )

    return ldes
