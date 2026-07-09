import json
import shlex

import ros2_launch_helpers as rlh
from launch import LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile, ParameterValue
from robot_mima_mkv30.model_utils import (
    DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS,
    DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS,
    DEFAULT_MIMA_CONTROLLER_REMAPPINGS,
)

# The default controller remappings make the standard launch configuration use the expected topic
# names.
# If a caller overrides one of these launch arguments, the caller replaces the whole remapping list
# for that controller and is responsible for providing every remapping it still needs.


def generate_launch_description() -> LaunchDescription:
    """
    When `use_sim_time` is true, the ros2_control_node is not started; Gazebo Sim takes care of
    starting the controller manager through the `gz_ros2_control` plugin.
    When `use_sim_time` is false, the ros2_control_node is started by this launch file.

    The controller names are fixed in this launch file. Users can tune the exposed spawner options,
    controller remappings, and controller manager node arguments, but they do not choose which
    controllers this launch file starts.
    """

    # Launch arguments with no default value must be provided by the caller.
    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
            DeclareLaunchArgument('params_file', description='Path to the ros2_control parameters file.'),
            DeclareLaunchArgument(
                'params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in params_file',
            ),
            DeclareLaunchArgument(
                'use_sim_time', choices=['True', 'true', 'False', 'false'], description='Use simulation clock if true'
            ),
            DeclareLaunchArgument(
                'controller_manager_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'joint_state_broadcaster_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the joint_state_broadcaster spawner',
            ),
            DeclareLaunchArgument(
                'mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the mima_controller spawner',
            ),
            DeclareLaunchArgument(
                'fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the fork_trajectory_controller spawner',
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
            OpaqueFunction(function=_launch_nodes),
        ]
    )


def _launch_nodes(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    # If use_sim_time is true, the ros2_control_node is not started; Gazebo Sim takes care of
    # starting the controller manager through the `gz_ros2_control` plugin.
    # If use_sim_time is false, the ros2_control_node is started by this launch file.
    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    # Full namespace for the nodes.
    robot_namespace = LaunchConfiguration('robot_namespace').perform(ctx)

    ldes: list[LaunchDescriptionEntity] = []

    if not use_sim_time_bool:
        ldes.append(
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                namespace=robot_namespace,
                parameters=[
                    ParameterFile(LaunchConfiguration('params_file'), allow_substs=False),
                    {'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)},
                ],
                # Add extra arguments like `--log-level debug`, `respawn`, ...
                **rlh.resolve_node_arguments(
                    LaunchConfiguration('controller_manager_node_args').perform(ctx),
                    extra_rejected_arguments={'namespace'},
                ),
            )
        )

    # Build the argv list for each spawner with the same order used by the spawner CLI help:
    # 1. Controller manager's name.
    # 2. The spawner options.
    # 3. --controller-ros-args: one string containing the ROS arguments for the controller node.
    # 4. Controller name

    # Full name of the controller manager.
    controller_manager = rlh.resolve_name(robot_namespace, 'controller_manager')

    common_controller_ros_args = f'--ros-args --param use_sim_time:={str(use_sim_time_bool).lower()}'

    joint_state_broadcaster_remappings = _to_controller_remap_args(
        _resolve_controller_remappings(
            'joint_state_broadcaster_controller_remappings',
            LaunchConfiguration('joint_state_broadcaster_controller_remappings').perform(ctx),
        )
    )

    joint_state_broadcaster_controller_spawner_arguments = ['--controller-manager', controller_manager]
    joint_state_broadcaster_controller_spawner_arguments.extend(
        _resolve_spawner_options(
            'joint_state_broadcaster_spawner_options',
            LaunchConfiguration('joint_state_broadcaster_spawner_options').perform(ctx),
        )
    )
    joint_state_broadcaster_controller_spawner_arguments.extend(
        [
            '--controller-ros-args',
            _join_controller_ros_args(common_controller_ros_args, joint_state_broadcaster_remappings),
            'joint_state_broadcaster',
        ]
    )

    mima_controller_remappings = _to_controller_remap_args(
        _resolve_controller_remappings(
            'mima_controller_remappings', LaunchConfiguration('mima_controller_remappings').perform(ctx)
        )
    )

    mima_controller_spawner_arguments = ['--controller-manager', controller_manager]
    mima_controller_spawner_arguments.extend(
        _resolve_spawner_options(
            'mima_controller_spawner_options', LaunchConfiguration('mima_controller_spawner_options').perform(ctx)
        )
    )
    mima_controller_spawner_arguments.extend(
        [
            '--controller-ros-args',
            _join_controller_ros_args(common_controller_ros_args, mima_controller_remappings),
            'mima_controller',
        ]
    )

    fork_trajectory_controller_remappings = _to_controller_remap_args(
        _resolve_controller_remappings(
            'fork_trajectory_controller_remappings',
            LaunchConfiguration('fork_trajectory_controller_remappings').perform(ctx),
        )
    )

    fork_trajectory_controller_spawner_arguments = ['--controller-manager', controller_manager]
    fork_trajectory_controller_spawner_arguments.extend(
        _resolve_spawner_options(
            'fork_trajectory_controller_spawner_options',
            LaunchConfiguration('fork_trajectory_controller_spawner_options').perform(ctx),
        )
    )
    fork_trajectory_controller_spawner_arguments.extend(
        [
            '--controller-ros-args',
            _join_controller_ros_args(common_controller_ros_args, fork_trajectory_controller_remappings),
            'fork_trajectory_controller',
        ]
    )

    # Add the spawner nodes after their argv lists have been built. A spawner is a short-lived
    # process: it asks controller_manager to load and configure one controller, then exits.
    ldes.extend(
        [
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=joint_state_broadcaster_controller_spawner_arguments,
            ),
            Node(package='controller_manager', executable='spawner', arguments=mima_controller_spawner_arguments),
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=fork_trajectory_controller_spawner_arguments,
            ),
        ]
    )

    return ldes


def _resolve_controller_remappings(
    launch_argument_name: str, launch_argument_value: str
) -> list[tuple[str, str]] | None:
    """
    Resolve one controller remapping launch argument from its JSON string value.

    Controller remappings are exposed as launch arguments, so callers pass them as strings.
    This helper keeps the JSON parsing boundary in one place and makes JSON syntax errors mention
    the launch argument name that contains the invalid value.
    """
    try:
        raw_remappings = json.loads(launch_argument_value)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Launch argument '{launch_argument_name}' must be valid JSON containing "
            f'a list of [from, to] remapping pairs.'
        ) from error

    return rlh.resolve_remappings(launch_argument_name, raw_remappings)


def _resolve_spawner_options(launch_argument_name: str, launch_argument_value: str) -> list[str]:
    """
    Read and validate the extra options for one controller spawner.

    ``launch_argument_name`` is the name of a launch argument such as
    ``mima_controller_spawner_options`` and is used only in error messages.
    ``launch_argument_value`` is the already resolved value of that launch argument. It is written
    like a small command line, for example ``--switch-timeout 30.0 --inactive``. This function uses
    ``shlex.split`` so quoted values are split with the same rules a shell would use.

    This function is the only place that decides which user-provided options are allowed to reach
    the ``spawner`` executable. Flag options are returned as one token. Options with a value are
    returned as two tokens: the option name and its value. If the user passes an unknown option,
    forgets the value for an option, or puts another option where the value should be, the function
    raises ``ValueError`` with the launch argument name in the message.

    The launch file does not let this argument set the controller name, controller manager,
    parameter files, or controller ROS arguments. Those values are built explicitly in
    ``_launch_nodes`` so every spawner call keeps the same shape.
    """
    allowed_spawner_flag_options = {
        '--load-only',
        '--inactive',
        '--unload-on-kill',
        '-u',
        '--switch-asap',
        '--no-switch-asap',
    }

    allowed_spawner_value_options = {'--controller-manager-timeout', '--switch-timeout', '--service-call-timeout'}

    allowed_options = sorted(allowed_spawner_flag_options | allowed_spawner_value_options)

    # Use shlex.split to handle quoted values and split the string into tokens.
    tokens = shlex.split(launch_argument_value)
    spawner_options: list[str] = []
    index = 0

    # Loop through the tokens and validate them against the allowed options.
    while index < len(tokens):
        token = tokens[index]

        # Check if the token is a flag option (no value required).
        if token in allowed_spawner_flag_options:
            spawner_options.append(token)
            index += 1
            continue

        # Check if the token is an option that requires a value.
        if token in allowed_spawner_value_options:
            # If the option requires a value, the next token must exist and must not start with '-'.
            if index + 1 >= len(tokens):
                raise ValueError(
                    f"Launch argument '{launch_argument_name}' option '{token}' requires a value. "
                    f'Allowed options are: {allowed_options}.'
                )

            value = tokens[index + 1]

            if value.startswith('-'):
                raise ValueError(
                    f"Launch argument '{launch_argument_name}' option '{token}' requires a value. "
                    f'Allowed options are: {allowed_options}.'
                )

            # If the option and its value are valid, add them to the spawner options list.
            spawner_options.extend([token, value])
            index += 2
            continue

        raise ValueError(
            f"Launch argument '{launch_argument_name}' contains unsupported spawner option '{token}'. "
            f'Allowed options are: {allowed_options}.'
        )

    return spawner_options


def _join_controller_ros_args(*args: str) -> str:
    return ' '.join(arg for arg in args if arg)


def _to_controller_remap_args(remappings: list[tuple[str, str]] | None) -> str:
    """
    Convert resolved controller remapping pairs to the string expected by ``--controller-ros-args``.
    """
    if not remappings:
        return ''

    return ' '.join(f'--remap {source_topic}:={target_topic}' for source_topic, target_topic in remappings)
