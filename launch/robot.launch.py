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
                description='Use simulation clock if true. This also enables the Gazebo ros2_control block.',
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
            # Insert the keys `robot_namespace` and `robot_prefix` into the launch context, with their
            # values, so they can be substituted in the parameter file if needed.
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

    ldes.extend(
        [
            # Include robot_state_publisher.
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
                    'robot_sim_file': LaunchConfiguration('robot_sim_file'),
                    'robot_rsp_node_args': LaunchConfiguration('robot_rsp_node_args'),
                }.items(),
            ),
            # Include bridge.
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
            ),
            # Include ros2_control.
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
                    'robot_controller_manager_node_args': LaunchConfiguration('robot_controller_manager_node_args'),
                    'robot_joint_state_broadcaster_spawner_options': LaunchConfiguration(
                        'robot_joint_state_broadcaster_spawner_options'
                    ),
                    'robot_mima_controller_spawner_options': LaunchConfiguration(
                        'robot_mima_controller_spawner_options'
                    ),
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
            ),
        ]
    )

    return ldes
