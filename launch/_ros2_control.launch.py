import json
import shlex
from typing import cast

import ros2_launch_helpers as rlh
from launch import LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction, SetLaunchConfiguration
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
    This launch file always starts the configured controller spawners.
    When `start_robot_controller_manager` is true, it also starts a local controller_manager.
    When `start_robot_controller_manager` is false, the spawners expect an existing controller_manager.

    The controller names are fixed in this launch file. Users can tune the exposed spawner options,
    controller remappings, and controller manager node arguments, but they do not choose which
    controllers this launch file starts.
    """

    # Launch arguments with no default value must be provided by the caller.
    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
            DeclareLaunchArgument(
                'robot_ros2_control_params_file', description='Path to the ros2_control parameters file.'
            ),
            DeclareLaunchArgument(
                'robot_ros2_control_params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in robot_ros2_control_params_file',
            ),
            DeclareLaunchArgument(
                'use_sim_time',
                choices=['True', 'true', 'False', 'false'],
                description='Use ROS time from /clock if true.',
            ),
            DeclareLaunchArgument(
                'start_robot_controller_manager',
                choices=['True', 'true', 'False', 'false'],
                description='Start the robot controller manager if true.',
            ),
            DeclareLaunchArgument(
                'robot_controller_manager_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            DeclareLaunchArgument(
                'robot_joint_state_broadcaster_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the joint_state_broadcaster spawner',
            ),
            DeclareLaunchArgument(
                'robot_mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the mima_controller spawner',
            ),
            DeclareLaunchArgument(
                'robot_fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Options for the fork_trajectory_controller spawner',
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
            # Insert `robot_type`, `robot_namespace` and `robot_prefix` into the launch context.
            # Their values can then be substituted in the parameter file if needed.
            SetLaunchConfiguration('robot_type', 'mima_mkv30'),
            rlh.SetRobotNamespace(
                namespace=LaunchConfiguration('namespace'),
                robot_name=LaunchConfiguration('robot_name'),
                output_context_key='robot_namespace',
            ),
            rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), output_context_key='robot_prefix'),
            OpaqueFunction(
                function=_launch_controller_manager,
                condition=IfCondition(LaunchConfiguration('start_robot_controller_manager')),
            ),
            OpaqueFunction(function=_launch_controller_spawners),
        ]
    )


def _get_spawner_arguments(
    use_sim_time: bool,
    fq_controller_manager_name: str,
    controller_name: str,
    spawner_options: list[str],
    remappings: list[tuple[str, str]] | None,
) -> list[str]:
    """
    Build the spawner CLI arguments for one controller.

    `fq_controller_manager_name` is the fully qualified controller manager name used by the
    spawner process. `controller_name` is the controller that this spawner loads and configures.
    """
    arguments = ['--controller-manager', fq_controller_manager_name]
    arguments.extend(spawner_options)

    controller_ros_args = f'--ros-args --param use_sim_time:={str(use_sim_time)}'

    if remappings:
        remapping_args = ' '.join(
            f'--remap {source_topic}:={target_topic}' for source_topic, target_topic in remappings
        )
        controller_ros_args = f'{controller_ros_args} {remapping_args}'

    arguments.extend(['--controller-ros-args', controller_ros_args, controller_name])

    return arguments


def _launch_controller_manager(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    params_allow_substs = perform_typed_substitution(
        ctx,
        normalize_typed_substitution(LaunchConfiguration('robot_ros2_control_params_file_allow_substs'), bool),
        bool,
    )

    return [
        rlh.RequireFile(path=LaunchConfiguration('robot_ros2_control_params_file')),
        Node(
            package='controller_manager',
            executable='ros2_control_node',
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=[
                ParameterFile(LaunchConfiguration('robot_ros2_control_params_file'), allow_substs=params_allow_substs),
                {'use_sim_time': ParameterValue(LaunchConfiguration('use_sim_time'), value_type=bool)},
            ],
            # ros2_control_node keeps its default node name, `controller_manager`.
            # Spawners target it later as `<robot_namespace>/controller_manager`.
            # Add extra arguments like `--log-level debug`, `respawn`, ...
            **rlh.resolve_node_arguments(
                LaunchConfiguration('robot_controller_manager_node_args').perform(ctx),
                extra_rejected_arguments={'namespace'},
            ),
        ),
    ]


def _launch_controller_spawners(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:

    # Full namespace for the nodes.
    robot_namespace = LaunchConfiguration('robot_namespace').perform(ctx)

    ldes: list[LaunchDescriptionEntity] = []

    use_sim_time = cast(
        bool,
        perform_typed_substitution(ctx, normalize_typed_substitution(LaunchConfiguration('use_sim_time'), bool), bool),
    )

    # Build the argv list for each spawner with the same order used by the spawner CLI help:
    # 1. Controller manager's name.
    # 2. The spawner options.
    # 3. --controller-ros-args: one string containing the ROS arguments for the controller node.
    # 4. Controller name

    # Full name of the controller manager.
    controller_manager = rlh.resolve_name(robot_namespace, 'controller_manager')

    joint_state_broadcaster_controller_spawner_arguments = _get_spawner_arguments(
        use_sim_time,
        controller_manager,
        'joint_state_broadcaster',
        _resolve_spawner_options(
            'robot_joint_state_broadcaster_spawner_options',
            LaunchConfiguration('robot_joint_state_broadcaster_spawner_options').perform(ctx),
        ),
        _resolve_controller_remappings(
            'robot_joint_state_broadcaster_controller_remappings',
            LaunchConfiguration('robot_joint_state_broadcaster_controller_remappings').perform(ctx),
        ),
    )

    mima_controller_spawner_arguments = _get_spawner_arguments(
        use_sim_time,
        controller_manager,
        'mima_controller',
        _resolve_spawner_options(
            'robot_mima_controller_spawner_options',
            LaunchConfiguration('robot_mima_controller_spawner_options').perform(ctx),
        ),
        _resolve_controller_remappings(
            'robot_mima_controller_remappings', LaunchConfiguration('robot_mima_controller_remappings').perform(ctx)
        ),
    )

    fork_trajectory_controller_spawner_arguments = _get_spawner_arguments(
        use_sim_time,
        controller_manager,
        'fork_trajectory_controller',
        _resolve_spawner_options(
            'robot_fork_trajectory_controller_spawner_options',
            LaunchConfiguration('robot_fork_trajectory_controller_spawner_options').perform(ctx),
        ),
        _resolve_controller_remappings(
            'robot_fork_trajectory_controller_remappings',
            LaunchConfiguration('robot_fork_trajectory_controller_remappings').perform(ctx),
        ),
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
    ``robot_mima_controller_spawner_options`` and is used only in error messages.
    ``launch_argument_value`` is the already resolved value of that launch argument.
    It is written like a small command line, for example ``--switch-timeout 30.0 --inactive``.
    This function uses ``shlex.split`` so quoted values are split with the same rules a shell would
    use.

    Flag options are returned as one token.
    Options with a value are returned as two tokens: the option name and its value.
    If the user passes an unknown option, forgets the value for an option, or puts another option
    where the value should be, the function raises ``ValueError`` with the launch argument name in
    the message.
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
    try:
        tokens = shlex.split(launch_argument_value)
    except ValueError as error:
        raise ValueError(
            f"Launch argument '{launch_argument_name}' must contain valid shell-style options: {error}"
        ) from error

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
