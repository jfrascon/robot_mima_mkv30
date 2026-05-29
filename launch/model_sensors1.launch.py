import os

import ros2_launch_helpers as rlh
from ament_index_python.packages import get_package_share_directory
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    OpaqueFunction,
    SetLaunchConfiguration,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.some_substitutions_type import SomeSubstitutionsType
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare

from launch import LaunchDescription, LaunchDescriptionEntity
from robot_mima_mkv30 import model_utils

ROBOT_MODEL = 'sensors1'


def generate_launch_description() -> LaunchDescription:
    """
    Build the launch description for the MiMA MKV30 model with sensors.
    """
    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description="Project's namespace"),
        DeclareLaunchArgument('robot_name', description="Robot's name"),
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(
                get_package_share_directory('robot_mima_mkv30'), 'config', f'model_{ROBOT_MODEL}', 'example_params.yaml'
            ),
            description='Path to the complete robot parameters file.',
        ),
        DeclareLaunchArgument(
            'params_file_allow_substs',
            choices=['True', 'true', 'False', 'false'],
            description='Allow ROS launch substitutions in params_file before including child launch files.',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            choices=['True', 'true', 'False', 'false'],
            description='Use simulation clock if true. This also enables the Gazebo ros2_control block.',
        ),
        DeclareLaunchArgument('local_odometry_frame', description='Odometry frame name without robot_prefix.'),
    ]

    # Declare the launch arguments for the xacro:args of the selected model
    # These launch arguments configure the robot model when building the robot description with
    # the xacro command.
    # Please, be aware that 'sim_file' is declared via this function, because
    # this file is used in the xacro model via a xacro argument.
    ldes.extend(model_utils.declare_launch_arguments(ROBOT_MODEL))

    ldes.extend(
        [
            DeclareLaunchArgument('rsp_node_name', default_value='robot_state_publisher', description='Node name'),
            DeclareLaunchArgument('bridge_node_name', default_value='bridge', description='Node name'),
            # ros2_control has its own remappings argument, next.
            DeclareLaunchArgument('node_remappings_map', default_value='{}', description=rlh.REMAPPINGS_DESC),
            DeclareLaunchArgument('node_options_map', default_value='{}', description=rlh.NODE_OPTIONS_DESC),
            DeclareLaunchArgument('node_logging_options_map', default_value='{}', description=rlh.LOGGING_OPTIONS_DESC),
            DeclareLaunchArgument(
                'ros2_control_remappings',
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
            SetLaunchConfiguration(
                'robot_odometry_frame',
                [LaunchConfiguration('robot_prefix'), LaunchConfiguration('local_odometry_frame')],
            ),
            # These values are fixed properties of this robot model. They are defined in
            # <pkg_robot_mima_mkv30>/urdf/includes/common.xacro and exposed in the launch context
            # so parameter YAML files can refer to the robot model instead of rebuilding prefixed
            # names or duplicating fixed geometry values.
            SetLaunchConfiguration('robot_base_frame', [LaunchConfiguration('robot_prefix'), 'base_footprint_link']),
            SetLaunchConfiguration(
                'robot_rear_left_wheel_rotation_joint',
                [LaunchConfiguration('robot_prefix'), 'rear_left_wheel_rotation_joint'],
            ),
            SetLaunchConfiguration(
                'robot_rear_right_wheel_rotation_joint',
                [LaunchConfiguration('robot_prefix'), 'rear_right_wheel_rotation_joint'],
            ),
            SetLaunchConfiguration(
                'robot_front_left_wheel_steering_joint',
                [LaunchConfiguration('robot_prefix'), 'front_left_wheel_steering_joint'],
            ),
            SetLaunchConfiguration(
                'robot_front_right_wheel_steering_joint',
                [LaunchConfiguration('robot_prefix'), 'front_right_wheel_steering_joint'],
            ),
            SetLaunchConfiguration('robot_fork_mast_joint', [LaunchConfiguration('robot_prefix'), 'fork_mast_joint']),
            SetLaunchConfiguration(
                'robot_fork_holder_joint', [LaunchConfiguration('robot_prefix'), 'fork_holder_joint']
            ),
            SetLaunchConfiguration('robot_fork_board_joint', [LaunchConfiguration('robot_prefix'), 'fork_board_joint']),
            SetLaunchConfiguration('robot_wheelbase', '1.7'),
            SetLaunchConfiguration('robot_front_wheel_track', '0.78'),
            SetLaunchConfiguration('robot_rear_wheel_track', '1.1'),
            SetLaunchConfiguration('robot_front_wheels_radius', '0.2285'),
            SetLaunchConfiguration('robot_rear_wheels_radius', '0.2795'),
            # Prepare params_file for consumers that need a concrete YAML path.
            OpaqueFunction(function=model_utils.process_params_file),
            _include_rsp(),
            _include_ros2_control(),
            _include_bridge(),
        ]
    )

    return LaunchDescription(ldes)


def _include_bridge() -> GroupAction:
    """
    Include the Gazebo bridge launch file for the sensors1 model.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'node_name': LaunchConfiguration('bridge_node_name'),
        'node_options_map': LaunchConfiguration('node_options_map'),
        'node_logging_options_map': LaunchConfiguration('node_logging_options_map'),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_bridge.launch.py'])
                ),
                launch_arguments={key: LaunchConfiguration(key) for key in launch_arguments}.items(),
            )
        ],
    )


def _include_rsp() -> GroupAction:
    """
    Include robot_state_publisher for the sensors1 model.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_model': ROBOT_MODEL,
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'node_name': LaunchConfiguration('rsp_node_name'),
        'node_remappings_map': LaunchConfiguration('node_remappings_map'),
        'node_options_map': LaunchConfiguration('node_options_map'),
        'node_logging_options_map': LaunchConfiguration('node_logging_options_map'),
        **model_utils.get_launch_configuration_entries(ROBOT_MODEL),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_rsp.launch.py'])
                ),
                launch_arguments={key: LaunchConfiguration(key) for key in launch_arguments}.items(),
            )
        ],
    )


def _include_ros2_control() -> GroupAction:
    """
    Include ros2_control preparation for the selected time mode.
    """
    launch_arguments: dict[SomeSubstitutionsType, SomeSubstitutionsType] = {
        'namespace': LaunchConfiguration('namespace'),
        'robot_name': LaunchConfiguration('robot_name'),
        'params_file': LaunchConfiguration('params_file'),
        'params_file_allow_substs': 'False',
        'use_sim_time': LaunchConfiguration('use_sim_time'),
        'ros2_control_remappings': LaunchConfiguration('ros2_control_remappings'),
    }

    return GroupAction(
        scoped=True,
        forwarding=False,
        launch_configurations=launch_arguments,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    PathJoinSubstitution([FindPackageShare('robot_mima_mkv30'), 'launch', '_ros2_control.launch.py'])
                ),
                launch_arguments={key: LaunchConfiguration(key) for key in launch_arguments}.items(),
            )
        ],
    )
