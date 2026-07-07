import ros2_launch_helpers as rlh
from launch import LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.some_substitutions_type import SomeSubstitutionsType
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
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

    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description="Project's namespace"),
        DeclareLaunchArgument('robot_model', choices=get_models(), description='Robot model variant.'),
        DeclareLaunchArgument('robot_name', default_value='mima_mkv30', description="Robot's name"),
        DeclareLaunchArgument(
            'params_file',
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
        # When params_file_allow_substs is true, the caller must insert into the context any
        # key-value pair used in the params_file.
        DeclareLaunchArgument(
            'params_file_allow_substs',
            default_value='True',
            choices=['True', 'true', 'False', 'false'],
            description='Allow ROS launch substitutions in params_file before including child launch files.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='False',
            choices=['True', 'true', 'False', 'false'],
            description='Use simulation clock if true. This also enables the Gazebo ros2_control block.',
        ),
        DeclareLaunchArgument(
            'model_xacro_args_file',
            default_value=PathJoinSubstitution(
                [
                    FindPackageShare('robot_mima_mkv30'),
                    'config',
                    ['model_', LaunchConfiguration('robot_model')],
                    'default_model_xacro_args.yaml',
                ]
            ),
            description='Path to the YAML file with xacro arguments loaded from configuration.',
        ),
        DeclareLaunchArgument(
            'sim_file',
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
            'bridge_config_file',
            default_value=PathJoinSubstitution(
                [
                    FindPackageShare('robot_mima_mkv30'),
                    'config',
                    ['model_', LaunchConfiguration('robot_model')],
                    'default_bridge.yaml',
                ]
            ),
            description='Path with the configuration for the bridge',
        ),
        DeclareLaunchArgument(
            'rsp_node_arguments',
            default_value='{"output": "both", "respawn": false}',
            description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
        ),
        DeclareLaunchArgument(
            'bridge_node_arguments',
            default_value='{"output": "both", "respawn": false}',
            description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
        ),
        DeclareLaunchArgument(
            'controller_manager_node_arguments',
            default_value='{"output": "both", "respawn": false}',
            description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
        ),
        DeclareLaunchArgument(
            'joint_state_broadcaster_spawner_options',
            default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
            description='Options for the joint_state_broadcaster controller spawner',
        ),
        DeclareLaunchArgument(
            'mima_controller_spawner_options',
            default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
            description='Options for the mima_controller controller spawner',
        ),
        DeclareLaunchArgument(
            'fork_trajectory_controller_spawner_options',
            default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
            description='Options for the fork_trajectory_controller controller spawner',
        ),
        DeclareLaunchArgument(
            'joint_state_broadcaster_controller_remappings',
            default_value=DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
            description='Remappings for the joint_state_broadcaster controller',
        ),
        DeclareLaunchArgument(
            'mima_controller_remappings',
            default_value=DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
            description='Remappings for the mima_controller controller',
        ),
        DeclareLaunchArgument(
            'fork_trajectory_controller_remappings',
            default_value=DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
            description='Remappings for the fork_trajectory_controller controller',
        ),
        rlh.SetRobotNamespace(
            namespace=LaunchConfiguration('namespace'),
            robot_name=LaunchConfiguration('robot_name'),
            robot_namespace_key='robot_namespace',
        ),
        rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), robot_prefix_key='robot_prefix'),
        rlh.ProcessParamsFile(
            params_file=LaunchConfiguration('params_file'),
            allow_substs=LaunchConfiguration('params_file_allow_substs'),
            output_params_file_key='params_file',
        ),
        _include_rsp(),
        _include_ros2_control(),
        _include_bridge(),
    ]

    return LaunchDescription(ldes)


def _include_bridge() -> GroupAction:
    """
    Include the bridge launch file with a new isolated launch context.

    The public model launch file prepares `params_file` first. This helper then
    passes the rendered parameter file and bridge node options to the internal
    bridge launch file.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'config_file': LaunchConfiguration('bridge_config_file'),
        'bridge_node_arguments': LaunchConfiguration('bridge_node_arguments'),
    }

    # Create an isolated launch context for the included launch file and seed that context with the
    # same keys passed to the include. The values in `launch_configurations` are resolved before the
    # isolated context is entered, so the `LaunchConfiguration` values below can still read from this
    # launch file. The included launch file then receives only the explicit `launch_arguments`.

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_bridge.launch.py'])
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )


def _include_rsp() -> GroupAction:
    """
    Include the robot_state_publisher launch file with a new isolated launch context.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_model': LaunchConfiguration('robot_model'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'model_xacro_args_file': LaunchConfiguration('model_xacro_args_file'),
        'sim_file': LaunchConfiguration('sim_file'),
        'rsp_node_arguments': LaunchConfiguration('rsp_node_arguments'),
    }

    # Create an isolated launch context for the included launch file and seed that context with the
    # same keys passed to the include. The values in `launch_configurations` are resolved before the
    # isolated context is entered, so the `LaunchConfiguration` values below can still read from this
    # launch file. The included launch file then receives only the explicit `launch_arguments`.

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_rsp.launch.py'])
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )


def _include_ros2_control() -> GroupAction:
    """
    Include ros2_control launch file with a new isolated launch context.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'controller_manager_node_arguments': LaunchConfiguration('controller_manager_node_arguments'),
        'joint_state_broadcaster_spawner_options': LaunchConfiguration('joint_state_broadcaster_spawner_options'),
        'mima_controller_spawner_options': LaunchConfiguration('mima_controller_spawner_options'),
        'fork_trajectory_controller_spawner_options': LaunchConfiguration('fork_trajectory_controller_spawner_options'),
        'joint_state_broadcaster_controller_remappings': LaunchConfiguration(
            'joint_state_broadcaster_controller_remappings'
        ),
        'mima_controller_remappings': LaunchConfiguration('mima_controller_remappings'),
        'fork_trajectory_controller_remappings': LaunchConfiguration('fork_trajectory_controller_remappings'),
    }

    # Create an isolated launch context for the included launch file and seed that context with the
    # same keys passed to the include. The values in `launch_configurations` are resolved before the
    # isolated context is entered, so the `LaunchConfiguration` values below can still read from this
    # launch file. The included launch file then receives only the explicit `launch_arguments`.

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )
