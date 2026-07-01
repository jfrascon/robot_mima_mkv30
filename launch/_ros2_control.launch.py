import json
import shlex

import ros2_launch_helpers as rlh
from launch import LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile

# Default remappings in the launch arguments `joint_state_broadcaster_controller_remappings`,
# `mima_controller_remappings`, and `fork_trajectory_controller_remappings` are always applied.
# The user can override any remapping individually.
# If a default remapping is left unchanged, it will be used by the proper controller.
DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS = '[["joint_states","joint_states"]]'

DEFAULT_MIMA_CONTROLLER_REMAPPINGS = (
    '[["~/reference","cmd_vel"],["~/odometry","odom"],["~/tf_odometry","/tf"],'
    '["~/controller_state","steering_controller_status"]]'
)

DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS = (
    '[["~/joint_trajectory","fork_trajectory"],'
    '["~/follow_joint_trajectory","fork_follow_joint_trajectory"],'
    '["~/controller_state","fork_trajectory_state"]]'
)


def generate_launch_description() -> LaunchDescription:
    """
    `params_file` points to the parameter YAML file that contains the configuration for the
    controller manager and the controllers.
    `params_file_allow_substs` indicates if dynamic substitutions are allowed in the parameter file.
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
                'controller_manager_node_arguments', default_value='{}', description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC
            ),
            DeclareLaunchArgument(
                'joint_state_broadcaster_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for joint_state_broadcaster',
            ),
            DeclareLaunchArgument(
                'mima_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for mima_controller',
            ),
            DeclareLaunchArgument(
                'fork_trajectory_controller_spawner_options',
                default_value='--switch-timeout 30.0 --service-call-timeout 30.0',
                description='Allowed spawner CLI options for fork_trajectory_controller',
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
            OpaqueFunction(function=_launch_ros2_control),
        ]
    )


def _launch_ros2_control(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    # If use_sim_time is true, the ros2_control_node is not started; Gazebo Sim takes care of
    # starting the controller manager through the `gz_ros2_control` plugin.
    # If use_sim_time is false, the ros2_control_node is started by this launch file.
    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)

    # Full namespace for the nodes.
    robot_namespace = LaunchConfiguration('robot_namespace').perform(ctx)

    ldes: list[LaunchDescriptionEntity] = []

    if not use_sim_time_bool:
        # ParameterFile can keep params_file as a LaunchConfiguration because launch_ros
        # resolves the file path later. In Jazzy, allow_substs is validated as a bool in the
        # constructor, so it must be evaluated here before the ParameterFile object is created.
        params_file_allow_substs = perform_typed_substitution(
            ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
        )

        ldes.append(
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                namespace=robot_namespace,
                parameters=[
                    ParameterFile(LaunchConfiguration('params_file'), allow_substs=params_file_allow_substs),
                    {'use_sim_time': use_sim_time_bool},
                ],
                # Add extra arguments like `--log-level debug`, `respawn`, ...
                **rlh.resolve_node_arguments(
                    LaunchConfiguration('controller_manager_node_arguments').perform(ctx),
                    default_arguments={'output': 'screen', 'respawn': False, 'ros_arguments': ['--log-level', 'info']},
                ),
            )
        )

    # Full name of the controller manager.
    controller_manager = rlh.resolve_name(robot_namespace, 'controller_manager')

    # Each spawner receives one --controller-ros-args value. That value must be one string
    # containing the ROS arguments for the controller node, the same way the CLI would quote
    # the value after --controller-ros-args.

    common_controller_ros_args = f'--ros-args --param use_sim_time:={str(use_sim_time_bool).lower()}'

    # Build the remapping fragments that will be passed to each controller through its
    # spawner. Defaults are always kept, and user-provided remappings can replace targets
    # or append new remappings.
    joint_state_broadcaster_remappings = _merge_controller_remappings(
        ctx, DEFAULT_JOINT_STATE_BROADCASTER_CONTROLLER_REMAPPINGS, 'joint_state_broadcaster_controller_remappings'
    )

    # Build the argv list for each spawner with the same order used by the spawner CLI help:
    # first the spawner options, then --controller-ros-args, and finally the controller name
    # as the positional argument.
    joint_state_broadcaster_controller_spawner_arguments = (
        ['--controller-manager', controller_manager]
        + _resolve_spawner_options(ctx, 'joint_state_broadcaster_spawner_options')
        + [
            '--controller-ros-args',
            common_controller_ros_args + ' ' + joint_state_broadcaster_remappings,
            'joint_state_broadcaster',
        ]
    )

    mima_controller_remappings = _merge_controller_remappings(
        ctx, DEFAULT_MIMA_CONTROLLER_REMAPPINGS, 'mima_controller_remappings'
    )

    mima_controller_spawner_arguments = (
        ['--controller-manager', controller_manager]
        + _resolve_spawner_options(ctx, 'mima_controller_spawner_options')
        + ['--controller-ros-args', common_controller_ros_args + ' ' + mima_controller_remappings, 'mima_controller']
    )

    fork_trajectory_controller_remappings = _merge_controller_remappings(
        ctx, DEFAULT_FORK_TRAJECTORY_CONTROLLER_REMAPPINGS, 'fork_trajectory_controller_remappings'
    )

    fork_trajectory_controller_spawner_arguments = (
        ['--controller-manager', controller_manager]
        + _resolve_spawner_options(ctx, 'fork_trajectory_controller_spawner_options')
        + [
            '--controller-ros-args',
            common_controller_ros_args + ' ' + fork_trajectory_controller_remappings,
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


def _resolve_controller_log_args(ctx: LaunchContext, launch_argument_name: str) -> str:
    """
    Read and validate the log arguments for one controller.

    ``launch_argument_name`` is the name of a launch argument whose value is written like a small
    command line. This function accepts only ``--log-level`` followed by one value. The value can be
    a general level such as ``debug`` or a logger-specific level such as
    ``botzilla.mima_controller:=debug``.

    The returned string is ready to be appended inside the single ``--controller-ros-args`` value
    passed to the spawner. An empty launch argument returns an empty string.
    """
    raw_value = LaunchConfiguration(launch_argument_name).perform(ctx)
    tokens = shlex.split(raw_value)
    allowed_log_levels = {'debug', 'info', 'warn', 'error', 'fatal'}
    log_args: list[str] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token != '--log-level':
            raise ValueError(
                f"Launch argument '{launch_argument_name}' contains unsupported controller log "
                f"option '{token}'. Only '--log-level <level>' is allowed."
            )

        if index + 1 >= len(tokens):
            raise ValueError(f"Launch argument '{launch_argument_name}' option '--log-level' requires a value.")

        value = tokens[index + 1]
        if value.startswith('-'):
            raise ValueError(f"Launch argument '{launch_argument_name}' option '--log-level' requires a value.")

        if ':=' in value:
            logger_name, level = value.rsplit(':=', 1)
            if not logger_name:
                raise ValueError(f"Launch argument '{launch_argument_name}' has an empty logger name in '{value}'.")
        else:
            level = value

        if level not in allowed_log_levels:
            raise ValueError(
                f"Launch argument '{launch_argument_name}' has unsupported log level '{level}'. "
                f'Allowed levels are: {sorted(allowed_log_levels)}.'
            )

        log_args.extend([token, value])
        index += 2

    return ' '.join(log_args)


def _resolve_spawner_options(ctx: LaunchContext, launch_argument_name: str) -> list[str]:
    """
    Read and validate the extra options for one controller spawner.

    ``launch_argument_name`` is the name of a launch argument such as
    ``mima_controller_spawner_options``. The value of that launch argument is written like a small
    command line, for example ``--switch-timeout 30.0 --inactive``. This function uses
    ``shlex.split`` so quoted values are split with the same rules a shell would use.

    This function is the only place that decides which user-provided options are allowed to reach
    the ``spawner`` executable. Flag options are returned as one token. Options with a value are
    returned as two tokens: the option name and its value. If the user passes an unknown option,
    forgets the value for an option, or puts another option where the value should be, the function
    raises ``ValueError`` with the launch argument name in the message.

    The launch file does not let this argument set the controller name, controller manager,
    parameter files, or controller ROS arguments. Those values are built explicitly in
    ``_launch_ros2_control`` so every spawner call keeps the same shape.
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

    raw_value = LaunchConfiguration(launch_argument_name).perform(ctx)
    # Use shlex.split to handle quoted values and split the string into tokens.
    tokens = shlex.split(raw_value)
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


def _merge_controller_remappings(
    ctx: LaunchContext, default_remappings_str: str, remappings_launch_argument: str
) -> str:
    """
    Build the ``--remap`` fragments for one controller spawner.

    ``default_remappings_str`` is the JSON string used as the default value of the controller
    remappings launch argument. ``remappings_launch_argument`` is the name of the launch argument
    that can add remappings or replace the target of an existing remapping. Both values use this
    JSON shape: ``[["from", "to"], ["from", "to"]]``.

    The default remappings are always loaded first. They are part of the robot launch contract and
    this function does not provide a way to delete them. User remappings are then merged by their
    source topic, which is the first item in each pair. If the user repeats a default source topic,
    the user value replaces the default target. If the user provides a new source topic, that
    remapping is appended after the defaults.

    A launch argument value of ``[]`` is valid and means that no user remappings are added. A launch
    argument value of ``null`` is also treated as no user remappings because
    ``rlh.resolve_remappings`` returns ``None`` for that value. Invalid JSON, empty strings, and
    malformed remapping pairs raise ``RuntimeError`` with the launch argument name in the message.

    The return value is one string because the spawner expects all controller ROS arguments as the
    value of one ``--controller-ros-args`` option. For example, two merged remappings are returned
    as ``--remap from1:=to1 --remap from2:=to2``.
    """
    remappings_str = LaunchConfiguration(remappings_launch_argument).perform(ctx)

    try:
        default_remappings = rlh.resolve_remappings(
            'default_' + remappings_launch_argument, json.loads(default_remappings_str)
        )
        if default_remappings is None:
            raise RuntimeError(
                f"Default remappings for '{remappings_launch_argument}' must be a JSON list of [from, to] pairs."
            )
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Default remappings for '{remappings_launch_argument}' must be valid JSON.") from error
    except ValueError as error:
        raise RuntimeError(str(error)) from error

    try:
        remapping_overrides = rlh.resolve_remappings(remappings_launch_argument, json.loads(remappings_str))
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Launch argument '{remappings_launch_argument}' must be a JSON list of [from, to] pairs."
        ) from error
    except ValueError as error:
        raise RuntimeError(str(error)) from error

    merged_remappings = {from_topic: f'--remap {from_topic}:={to_topic}' for from_topic, to_topic in default_remappings}

    if remapping_overrides is not None:
        for from_topic, to_topic in remapping_overrides:
            merged_remappings[from_topic] = f'--remap {from_topic}:={to_topic}'

    return ' '.join(merged_remappings.values())
