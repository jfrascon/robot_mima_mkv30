import json
from typing import List

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
    Prepare ros2_control from the selected time mode.

    The model wrapper prepares the final controller YAML file before including
    this launch file. In simulation, the URDF contains the gz_ros2_control
    plugin and that plugin receives the final YAML file path through the
    <parameters> tag.

    This launch file also starts the controller spawners required by this robot
    model. The controller names are intentionally listed in this launch file.

    In real hardware mode, this launch file launches controller_manager's
    `ros2_control_node` before starting the controller spawners.

    `use_sim_time:=true` selects simulation mode. `use_sim_time:=false` selects
    real-time mode.
    """
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                'use_sim_time',
                default_value='False',
                choices=['True', 'true', 'False', 'false'],
                description='Use simulation time for ros2_control nodes launched by this file.',
            ),
            DeclareLaunchArgument(
                'controller_config_file', default_value='', description='Path to the prepared controller YAML file.'
            ),
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument(
                'robot_name', default_value='mima_mkv30', description='The unique name for the robot'
            ),
            DeclareLaunchArgument('robot_model', default_value='base'),
            DeclareLaunchArgument(
                'controller_remappings',
                default_value='{}',
                description=(
                    'JSON object indexed by controller name. Entries override the default '
                    'remappings for the matching controller.'
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
            OpaqueFunction(
                function=rlh.set_robot_prefix,
                kwargs={'robot_name_key': 'robot_name', 'robot_prefix_key': 'robot_prefix'},
            ),
            OpaqueFunction(function=_launch_ros2_control),
        ]
    )


def _launch_ros2_control(ctx: LaunchContext) -> List[LaunchDescriptionEntity]:
    """
    Launch ros2_control actions for the selected time mode.

    If `use_sim_time` is true, Gazebo creates the controller manager through the
    `gz_ros2_control` plugin declared in the URDF. In that case this function
    does not launch `ros2_control_node`; it only launches the controller spawner
    processes against Gazebo's controller manager in the robot namespace.

    If `use_sim_time` is false, this function launches the real
    `controller_manager` node with the prepared controller YAML file. It then
    launches the same controller spawner processes against the controller
    manager node created in the robot namespace.

    The controller receives fully expanded frame and joint names. Source code in
    the controller should not add robot-specific prefixes to those names.
    """

    controller_config_file = LaunchConfiguration('controller_config_file').perform(ctx)

    if not controller_config_file:
        raise RuntimeError('controller_config_file must point to the prepared controller YAML file.')

    use_sim_time_lc = LaunchConfiguration('use_sim_time')
    use_sim_time_bool = perform_typed_substitution(ctx, normalize_typed_substitution(use_sim_time_lc, bool), bool)
    robot_namespace = LaunchConfiguration('robot_namespace').perform(ctx).strip('/')

    if not robot_namespace:
        raise RuntimeError('robot_namespace cannot be empty')

    # The spawner accepts a controller manager node name. Use an absolute ROS name here so the
    # target controller manager is explicit and independent of the namespace in which the spawner
    # might be launched (there is no real need to launch the spawner in a specific namespace since
    # its lifetime is very short and it only serves to launch the controllers in the target
    # controller manager).
    controller_manager = rlh.resolve_name('/', rlh.resolve_name(robot_namespace, 'controller_manager'))

    ldes: List[LaunchDescriptionEntity] = []

    if not use_sim_time_bool:
        ldes.append(
            Node(
                package='controller_manager',
                executable='ros2_control_node',
                namespace=LaunchConfiguration('robot_namespace'),
                parameters=[
                    ParameterFile(controller_config_file, allow_substs=True),
                    {'use_sim_time': use_sim_time_bool},
                ],
                output='screen',
            )
        )

    default_controller_remappings = {
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

    controller_remappings = _merge_controller_remappings(
        default_controller_remappings,
        _parse_controller_remappings(LaunchConfiguration('controller_remappings').perform(ctx)),
    )

    use_sim_time_arg = f'use_sim_time:={str(use_sim_time_bool).lower()}'

    joint_state_broadcaster_controller_arguments = [
        'joint_state_broadcaster',
        '--controller-manager',
        controller_manager,
    ]

    joint_state_broadcaster_ros_args = ['--ros-args', '--param', use_sim_time_arg]

    # Extend the controller ROS arguments with remappings provided for this controller.
    joint_state_broadcaster_ros_args.extend(
        _controller_remap_arguments(controller_remappings, 'joint_state_broadcaster')
    )

    # The spawner argparse definition expects one value after `--controller-ros-args`.
    # Keep the full ROS argument list as one string so argparse does not treat the first
    # `--ros-args` token as a new spawner option.
    joint_state_broadcaster_controller_arguments.extend(
        ['--controller-ros-args', ' '.join(joint_state_broadcaster_ros_args)]
    )

    mima_controller_arguments = ['mima_controller', '--controller-manager', controller_manager]

    mima_controller_ros_args = ['--ros-args', '--param', use_sim_time_arg]

    # Extend the controller ROS arguments with remappings provided for this controller.
    mima_controller_ros_args.extend(_controller_remap_arguments(controller_remappings, 'mima_controller'))

    mima_controller_arguments.extend(['--controller-ros-args', ' '.join(mima_controller_ros_args)])

    fork_trajectory_controller_arguments = ['fork_trajectory_controller', '--controller-manager', controller_manager]

    fork_trajectory_controller_ros_args = ['--ros-args', '--param', use_sim_time_arg]

    # Extend the controller ROS arguments with remappings provided for this controller.
    fork_trajectory_controller_ros_args.extend(
        _controller_remap_arguments(controller_remappings, 'fork_trajectory_controller')
    )

    fork_trajectory_controller_arguments.extend(
        ['--controller-ros-args', ' '.join(fork_trajectory_controller_ros_args)]
    )

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


# Helper functions


def _controller_remap_arguments(controller_remappings: dict[str, list[str]], controller_name: str) -> list[str]:
    """
    Convert one controller remapping list to ROS remap argument fragments.
    """
    remap_arguments: list[str] = []

    for remapping in controller_remappings.get(controller_name, []):
        remap_arguments.extend(['--remap', remapping])

    return remap_arguments


def _merge_controller_remappings(
    default_controller_remappings: dict[str, list[str]], controller_remapping_overrides: dict[str, list[str]]
) -> dict[str, list[str]]:
    """
    Apply user-provided remapping lists as per-controller replacements.

    The model launch files pass `{}` by default, so this function keeps all
    default remappings unless the user provides an entry for a controller. When
    the user provides an entry, that controller list replaces the default list.
    """
    controller_remappings = {name: list(remappings) for name, remappings in default_controller_remappings.items()}
    for controller_name, remappings in controller_remapping_overrides.items():
        controller_remappings[controller_name] = list(remappings)

    return controller_remappings


def _parse_controller_remappings(raw_value: str) -> dict[str, list[str]]:
    """
    Parse and validate the JSON string used by `controller_remappings`.

    The expected value is a JSON object indexed by controller name. Each value
    is a list of ROS remapping strings written as `from:=to`.
    """
    try:
        config = json.loads(raw_value)
    except json.JSONDecodeError as error:
        raise RuntimeError('controller_remappings must be a valid JSON object.') from error

    if not isinstance(config, dict):
        raise RuntimeError('controller_remappings must be a JSON object indexed by controller name.')

    controller_remappings: dict[str, list[str]] = {}
    for controller_name, remappings in config.items():
        if not isinstance(controller_name, str) or not controller_name:
            raise RuntimeError('controller_remappings keys must be non-empty controller names.')

        if not isinstance(remappings, list):
            raise RuntimeError(f"controller_remappings entry for controller '{controller_name}' must be a JSON list.")

        controller_remappings[controller_name] = []

        for index, remapping in enumerate(remappings):
            if not isinstance(remapping, str):
                raise RuntimeError(
                    f"controller_remappings item {index} for controller '{controller_name}' must be a string."
                )

            try:
                original_topic, new_topic = remapping.split(':=', maxsplit=1)
            except ValueError as error:
                raise RuntimeError(
                    f"controller_remappings item {index} for controller '{controller_name}' must use 'from:=to' syntax."
                ) from error

            if not original_topic:
                raise RuntimeError(
                    f"controller_remappings item {index} for controller '{controller_name}' must have "
                    "a non-empty 'from'."
                )

            if not new_topic:
                raise RuntimeError(
                    f"controller_remappings item {index} for controller '{controller_name}' must have a non-empty 'to'."
                )

            controller_remappings[controller_name].append(remapping)

    return controller_remappings
