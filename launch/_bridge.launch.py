import ros2_launch_helpers as rlh
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile, ParameterValue
from robotics_description.bridge_configurations import create_battery_bridges


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal Gazebo bridge launch description for one robot model.

    This launch file is meant to be included by `robot.launch.py`, but can
    be run directly as well. When robot_bridge_params_file_allow_substs is true, the caller
    can pass the launch keys used by the parameter file as extra CLI arguments
    even if this launch file does not declare those keys.

    When use_sim_time is false, this launch file skips the bridge node because
    the bridge is only used in simulation.
    """

    return LaunchDescription(
        [
            DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
            DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
            DeclareLaunchArgument(
                'robot_bridge_params_file', description='Path to the complete robot parameter YAML file.'
            ),
            DeclareLaunchArgument(
                'robot_bridge_params_file_allow_substs',
                choices=['True', 'true', 'False', 'false'],
                description='Allow ROS launch substitutions in robot_bridge_params_file',
            ),
            DeclareLaunchArgument(
                'use_sim_time', choices=['True', 'true', 'False', 'false'], description='Use simulation clock if true'
            ),
            DeclareLaunchArgument(
                'robot_bridge_config_file', description='Path to the robot bridge configuration file.'
            ),
            DeclareLaunchArgument(
                'robot_bridge_node_args',
                default_value='{"output": "both", "ros_arguments": ["--log-level", "info"]}',
                description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC,
            ),
            rlh.RequireFile(path=LaunchConfiguration('robot_bridge_params_file')),
            # Insert the keys `robot_namespace` and `robot_prefix` into the launch context, with
            # their values, so they can be substituted in the parameter file if needed.
            rlh.SetRobotNamespace(
                namespace=LaunchConfiguration('namespace'),
                robot_name=LaunchConfiguration('robot_name'),
                output_context_key='robot_namespace',
            ),
            rlh.SetRobotPrefix(robot_name=LaunchConfiguration('robot_name'), output_context_key='robot_prefix'),
            OpaqueFunction(function=_launch_node, condition=IfCondition(LaunchConfiguration('use_sim_time'))),
        ]
    )


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch the bridge for one robot instance.

    The bridge is only useful when Gazebo is running, so this function is only executed when
    `use_sim_time` is true.
    """

    params_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('robot_bridge_params_file_allow_substs'), bool), bool
    )

    return [
        Node(
            package='ros_gz_bridge',
            executable='bridge_node',
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=[
                ParameterFile(LaunchConfiguration('robot_bridge_params_file'), allow_substs=params_allow_substs),
                # `expand_gz_topic_names` is always true because Gazebo topics are expected to
                # include the robot namespace so multiple robots can run in the same simulation.
                # `override_frame_id` is set to an empty string because Gazebo plugins publish the
                # required frame_id.
                {
                    'use_sim_time': True,
                    'config_file': ParameterValue(LaunchConfiguration('robot_bridge_config_file'), value_type=str),
                    'expand_gz_topic_names': True,
                    'override_frame_id': '',
                },
                # The bridges for the battery are not configured in the reusable bridge YAML file
                # because the battery plugin does not allow setting the topic name.
                create_battery_bridges(
                    model_name=LaunchConfiguration('robot_name').perform(ctx),
                    battery_name='main_battery',
                    battery_state_ros_topic='main_battery/state',
                    battery_recharge_start_ros_topic='main_battery/recharge/start',
                    battery_recharge_stop_ros_topic='main_battery/recharge/stop',
                ),
            ],
            **rlh.resolve_node_arguments(
                LaunchConfiguration('robot_bridge_node_args').perform(ctx), extra_rejected_arguments={'namespace'}
            ),
        )
    ]
