import json
from pathlib import Path

import ros2_launch_helpers as rlh
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile

from launch import LaunchDescription, LaunchDescriptionEntity


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal ros2_control launch description for one robot instance.

    This launch file receives one ros2_control parameter file through
    `params_file`. The file may already be rendered by a model launch file, or it
    may be rendered here when `params_file_allow_substs` is true.

    `use_sim_time` is required because it selects the ros2_control runtime path
    and because this launch file passes the same value to the ros2_control nodes
    that it starts or asks the spawner to start.

    When `use_sim_time` is false, this launch file starts
    controller_manager's `ros2_control_node`. When `use_sim_time` is true,
    Gazebo starts the controller manager through gz_ros2_control and this launch
    file only starts controller spawners.

    The controller names are intentionally listed in this launch file.
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
                'ros2_control_remappings',
                default_value='{}',
                description=(
                    'JSON object indexed by known controller name. Entries override the '
                    'default remappings for the matching controller.'
                ),
            ),
            OpaqueFunction(
                function=rlh.set_robot_namespace,
                kwargs={
                    'namespace_key': 'namespace',
                    'robot_name_key': 'robot_name',
                    'robot_namespace_key': 'robot_namespace',
                },
            ),
            OpaqueFunction(function=_launch_ros2_control),
        ]
    )


def _launch_ros2_control(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch ros2_control_node when needed and start the controller spawners.

    If `use_sim_time` is true, Gazebo creates the controller manager through the
    `gz_ros2_control` plugin declared in the URDF. In that case this function
    does not launch `ros2_control_node`; it only launches the controller spawner
    processes against Gazebo's controller manager in the robot namespace.

    If `use_sim_time` is false, this function launches
    `controller_manager` with the parameter YAML file. It then launches the
    same controller spawner processes against the controller
    manager node created in the robot namespace.

    The controller receives fully expanded frame and joint names. Source code in
    the controller should not add robot-specific prefixes to those names.
    """

    params_file = rlh.resolve_file(LaunchConfiguration('params_file').perform(ctx))
    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    if not Path(params_file).is_file():
        raise FileNotFoundError(f"Params file '{params_file}' does not exist.")

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)
    robot_namespace = LaunchConfiguration('robot_namespace').perform(ctx)

    controller_manager = rlh.resolve_name(robot_namespace, 'controller_manager')

    ldes: list[LaunchDescriptionEntity] = []

    # When Gazebo is not running the ros2_control plugin, this launch file starts
    # controller_manager directly. The launch argument use_sim_time is passed as
    # a node parameter because use_sim_time is not configured in the YAML file.
    if not use_sim_time_bool:
        ldes.append(
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                namespace=robot_namespace,
                parameters=[
                    ParameterFile(params_file, allow_substs=params_file_allow_substs),
                    {'use_sim_time': use_sim_time_bool},
                ],
                output='screen',
            )
        )

    default_ros2_control_remappings = {
        'joint_state_broadcaster': ['joint_states:=joint_states'],
        'mima_controller': [
            '~/reference:=cmd_vel',
            '~/odometry:=odom',
            '~/tf_odometry:=/tf',
            '~/controller_state:=steering_controller_status',
        ],
        'fork_trajectory_controller': [
            '~/joint_trajectory:=fork_trajectory',
            '~/follow_joint_trajectory:=fork_follow_joint_trajectory',
            '~/controller_state:=fork_trajectory_state',
        ],
    }

    remappings = _merge_remappings(
        default_ros2_control_remappings, _parse_remappings(LaunchConfiguration('ros2_control_remappings').perform(ctx))
    )

    use_sim_time_arg = f'use_sim_time:={str(use_sim_time_bool).lower()}'

    common_spawner_arguments = [
        '--controller-manager',
        controller_manager,
        '--switch-timeout',
        '30.0',
        '--service-call-timeout',
        '30.0',
    ]
    common_controller_ros_args = ['--ros-args', '--param', use_sim_time_arg]

    joint_state_broadcaster_ros_args = common_controller_ros_args + _get_remappings_ros_args(
        remappings.get('joint_state_broadcaster', [])
    )

    joint_state_broadcaster_controller_arguments = [
        'joint_state_broadcaster',
        *common_spawner_arguments,
        '--controller-ros-args',
        ' '.join(joint_state_broadcaster_ros_args),
    ]

    mima_controller_ros_args = common_controller_ros_args + _get_remappings_ros_args(
        remappings.get('mima_controller', [])
    )

    mima_controller_arguments = [
        'mima_controller',
        *common_spawner_arguments,
        '--controller-ros-args',
        ' '.join(mima_controller_ros_args),
    ]

    fork_trajectory_controller_ros_args = common_controller_ros_args + _get_remappings_ros_args(
        remappings.get('fork_trajectory_controller', [])
    )

    fork_trajectory_controller_arguments = [
        'fork_trajectory_controller',
        *common_spawner_arguments,
        '--controller-ros-args',
        ' '.join(fork_trajectory_controller_ros_args),
    ]

    ldes.extend(
        [
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=joint_state_broadcaster_controller_arguments,
                output='screen',
            ),
            Node(
                package='controller_manager', executable='spawner', arguments=mima_controller_arguments, output='screen'
            ),
            Node(
                package='controller_manager',
                executable='spawner',
                arguments=fork_trajectory_controller_arguments,
                output='screen',
            ),
        ]
    )

    return ldes


def _get_remappings_ros_args(remappings: list[str]) -> list[str]:
    """
    Convert one controller remapping list to ROS remap argument fragments.

    Controller spawners receive controller-specific ROS arguments as one string
    after `--controller-ros-args`. This helper expands each compact remapping
    string into the argv fragments expected by ROS.

    Example:
    `['~/reference:=cmd_vel', '~/odometry:=odom']` becomes
    `['--remap', '~/reference:=cmd_vel', '--remap', '~/odometry:=odom']`.
    """
    remap_arguments: list[str] = []

    for remapping in remappings:
        # Each remapping must be preceded by its own `--remap` flag. A single
        # `--remap` flag followed by several remappings is not valid ROS argv.
        remap_arguments.extend(['--remap', remapping])

    return remap_arguments


def _merge_remappings(
    default_ros2_control_remappings: dict[str, list[str]], controller_remapping_overrides: dict[str, list[str]]
) -> dict[str, list[str]]:
    """
    Apply user-provided remapping overrides to the default ros2_control remappings.

    The model launch files pass `{}` by default, so all default remappings are
    kept unless the user provides an entry for a controller. A user-provided
    entry replaces the complete list for that controller; it is not appended to
    the default list. Unknown controller names raise an error instead of being
    ignored.

    A new mapping is returned so the default mapping owned by this launch file is
    not mutated while applying per-launch overrides.
    """
    ros2_control_remappings = {name: list(remappings) for name, remappings in default_ros2_control_remappings.items()}

    for controller_name, remappings in controller_remapping_overrides.items():
        if controller_name not in ros2_control_remappings:
            raise RuntimeError(
                f"ros2_control_remappings has an unknown controller '{controller_name}'. "
                f'Known controllers: {sorted(ros2_control_remappings.keys())}.'
            )

        ros2_control_remappings[controller_name] = list(remappings)

    return ros2_control_remappings


def _parse_remappings(raw_value: str) -> dict[str, list[str]]:
    """
    Parse and validate the JSON string used by `ros2_control_remappings`.

    The expected value is a JSON object indexed by controller name. Each value
    is a list of ROS remapping strings written as `from:=to`.

    This validation happens before launching any spawner process, so malformed
    remapping configuration fails at launch time with a message that names the
    controller and item that must be fixed.
    """
    try:
        config = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise RuntimeError('ros2_control_remappings must be a valid JSON object.') from error

    if not isinstance(config, dict):
        raise RuntimeError('ros2_control_remappings must be a JSON object indexed by controller name.')

    ros2_control_remappings: dict[str, list[str]] = {}

    for controller_name, remappings in config.items():
        if not isinstance(controller_name, str) or not controller_name:
            raise RuntimeError('ros2_control_remappings keys must be non-empty controller names.')

        if not isinstance(remappings, list):
            raise RuntimeError(f"ros2_control_remappings entry for controller '{controller_name}' must be a JSON list.")

        ros2_control_remappings[controller_name] = []

        for index, remapping in enumerate(remappings):
            if not isinstance(remapping, str):
                raise RuntimeError(
                    f"ros2_control_remappings item {index} for controller '{controller_name}' must be a string."
                )

            try:
                original_topic, new_topic = remapping.split(':=', maxsplit=1)
            except ValueError as error:
                raise RuntimeError(
                    f"ros2_control_remappings item {index} for controller '{controller_name}' must use "
                    "'from:=to' syntax."
                ) from error

            if not original_topic:
                raise RuntimeError(
                    f"ros2_control_remappings item {index} for controller '{controller_name}' must have "
                    "a non-empty 'from'."
                )

            if not new_topic:
                raise RuntimeError(
                    f"ros2_control_remappings item {index} for controller '{controller_name}' must have "
                    "a non-empty 'to'."
                )

            ros2_control_remappings[controller_name].append(remapping)

    return ros2_control_remappings
