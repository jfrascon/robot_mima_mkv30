import ros2_launch_helpers as rlh
from launch import LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
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
            'ros_gz_bridge_config_file',
            default_value=PathJoinSubstitution(
                [
                    FindPackageShare('robot_mima_mkv30'),
                    'config',
                    ['model_', LaunchConfiguration('robot_model')],
                    'default_ros_gz_bridge.yaml',
                ]
            ),
            description='Path with the configuration for the bridge',
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
            output_context_key='robot_namespace',
        ),
        rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), output_context_key='robot_prefix'),
        rlh.RequireFile(path=LaunchConfiguration('params_file')),
        rlh.RenderParamsFile(
            params_file=LaunchConfiguration('params_file'),
            output_context_key='params_file',
            condition=IfCondition(LaunchConfiguration('params_file_allow_substs')),
        ),
        _include_robot_state_publisher(),
        _include_ros2_control(),
        _include_ros_gz_bridge(),
    ]

    return LaunchDescription(ldes)


def _include_robot_state_publisher() -> GroupAction:
    """
    Include the robot_state_publisher launch file with a new isolated launch context.
    """
    # With `scoped=True`, `GroupAction` creates an isolated launch context for the included launch
    # file.
    # With `forwarding=False`, that isolated context does not automatically inherit launch
    # configurations from this launch file.
    # The `launch_configurations` argument below explicitly populates the isolated context with the
    # keys that the included launch file is allowed to see.
    # The `launch_arguments` passed to `IncludeLaunchDescription` must then read values from that
    # isolated context, not from the original context.

    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_model': LaunchConfiguration('robot_model'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'model_xacro_args_file': LaunchConfiguration('model_xacro_args_file'),
        'sim_file': LaunchConfiguration('sim_file'),
    }

    # In the original launch context the public key is `robot_state_publisher_node_args`.
    # The included `_robot_state_publisher.launch.py` does not declare that key; it declares
    # `node_args`.
    #
    # For that reason this helper uses two mappings:
    #
    # - `launch_configurations` populates the new isolated context. It reads
    #   `robot_state_publisher_node_args`
    #   from this launch file and stores that value under `node_args` in the isolated context.
    # - `launch_arguments` is passed to `IncludeLaunchDescription`. It must read `node_args`
    #   from the isolated context, because `robot_state_publisher_node_args` is not available there.
    #
    # Value flow:
    # `robot_state_publisher_node_args` in robot.launch.py -> `node_args` in the isolated context ->
    # `node_args` argument declared by _robot_state_publisher.launch.py.

    launch_configurations = {**launch_mappings, 'node_args': LaunchConfiguration('robot_state_publisher_node_args')}
    launch_arguments = {**launch_mappings, 'node_args': LaunchConfiguration('node_args')}

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_configurations,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution(
                        [FindPackageShare('robot_mima_mkv30'), 'launch', '_robot_state_publisher.launch.py']
                    )
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )


def _include_ros_gz_bridge() -> GroupAction:
    """
    Include the bridge launch file with a new isolated launch context.

    The public model launch file prepares `params_file` first. This helper then
    passes the rendered parameter file and bridge node options to the internal
    bridge launch file.
    """
    # With `scoped=True`, `GroupAction` creates an isolated launch context for the included launch
    # file.
    # With `forwarding=False`, that isolated context does not automatically inherit launch
    # configurations from this launch file.
    # The `launch_configurations` argument below explicitly populates the isolated context with the
    # keys that the included launch file is allowed to see.
    # The `launch_arguments` passed to `IncludeLaunchDescription` must then read values from that
    # isolated context, not from the original context.

    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
    }

    # In the original launch context the public keys are `ros_gz_bridge_config_file` and
    # `ros_gz_bridge_node_args`. The included `_ros_gz_bridge.launch.py` does not declare those
    # keys; it declares `config_file` and `node_args`.
    #
    # For that reason this helper uses two mappings:
    #
    # - `launch_configurations` populates the new isolated context. It reads
    #   `ros_gz_bridge_config_file` and `ros_gz_bridge_node_args` from this launch file and stores those
    #   values under `config_file` and `node_args` in the isolated context.
    # - `launch_arguments` is passed to `IncludeLaunchDescription`. It must read `config_file` and
    #   `node_args` from the isolated context, because `ros_gz_bridge_config_file` and
    #   `ros_gz_bridge_node_args` are not available there.
    #
    # Value flow:
    # `ros_gz_bridge_config_file` in robot.launch.py -> `config_file` in the isolated context ->
    # `config_file` argument declared by _ros_gz_bridge.launch.py.
    # `ros_gz_bridge_node_args` in robot.launch.py -> `node_args` in the isolated context ->
    # `node_args` argument declared by _ros_gz_bridge.launch.py.

    launch_configurations = {
        **launch_mappings,
        'config_file': LaunchConfiguration('ros_gz_bridge_config_file'),
        'node_args': LaunchConfiguration('ros_gz_bridge_node_args'),
    }

    launch_arguments = {
        **launch_mappings,
        'config_file': LaunchConfiguration('config_file'),
        'node_args': LaunchConfiguration('node_args'),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_configurations,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros_gz_bridge.launch.py'])
                ),
                launch_arguments=launch_arguments.items(),
            )
        ],
    )


def _include_ros2_control() -> GroupAction:
    """
    Include ros2_control launch file with a new isolated launch context.
    """
    # With `scoped=True`, `GroupAction` creates an isolated launch context for the included launch
    # file.
    # With `forwarding=False`, that isolated context does not automatically inherit launch
    # configurations from this launch file.
    # The `launch_configurations` argument below explicitly populates the isolated context with the
    # keys that the included launch file is allowed to see.
    # The `launch_arguments` passed to `IncludeLaunchDescription` must then read values from that
    # isolated context, not from the original context.

    launch_mappings: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
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

    # The keys in `launch_mappings` are the same keys declared by `_ros2_control.launch.py`.
    # The included launch file receives those same keys, so this include does not need separate
    # `launch_configurations` and `launch_arguments` mappings.

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_mappings,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
                ),
                launch_arguments=launch_mappings.items(),
            )
        ],
    )
