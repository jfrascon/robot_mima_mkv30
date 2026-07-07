import ros2_launch_helpers as rlh
from launch import LaunchContext, LaunchDescription, LaunchDescriptionEntity
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from launch_ros.parameters_type import SomeParameters
from robotics_description.bridge_configurations import create_battery_bridges


def generate_launch_description() -> LaunchDescription:
    """
    Build the internal Gazebo bridge launch description for one robot model.

    This launch file is meant to be included by `robot.launch.py`, but can
    be run directly as well. When params_file_allow_substs is true, the caller
    can pass the launch keys used by the parameter file as extra CLI arguments
    even if this launch file does not declare those keys.

    When use_sim_time is false, this launch file skips the bridge node because
    the ROS-GZ bridge is only used in simulation.
    """

    ldes: list[LaunchDescriptionEntity] = [
        DeclareLaunchArgument('namespace', default_value='', description='Project namespace'),
        DeclareLaunchArgument('robot_name', description='The unique name for the robot'),
        DeclareLaunchArgument('params_file', description='Path to params file'),
        DeclareLaunchArgument(
            'params_file_allow_substs',
            choices=['True', 'true', 'False', 'false'],
            description='Allow ROS launch substitutions in params_file',
        ),
        DeclareLaunchArgument(
            'use_sim_time', choices=['True', 'true', 'False', 'false'], description='Use simulation clock if true'
        ),
        DeclareLaunchArgument('config_file', description='Path with the configuration for the bridge'),
        DeclareLaunchArgument(
            'bridge_node_arguments', default_value='{}', description=rlh.LAUNCH_ACTION_ARGUMENTS_DESC
        ),
        rlh.SetRobotNamespace(
            namespace=LaunchConfiguration('namespace'),
            robot_name=LaunchConfiguration('robot_name'),
            robot_namespace_key='robot_namespace',
        ),
        OpaqueFunction(function=_launch_node, condition=IfCondition(LaunchConfiguration('use_sim_time'))),
    ]

    return LaunchDescription(ldes)


def _launch_node(ctx: LaunchContext) -> list[LaunchDescriptionEntity]:
    """
    Launch the ROS-GZ bridge for one robot instance.

    The bridge is only useful when Gazebo is running, so this function is only executed when
    `use_sim_time` is true.
    """

    # launch_ros.parameter_descriptions.ParameterFile accepts param_file as FilePath or
    # SomeSubstitutionsType, so params_file can stay as a LaunchConfiguration and be resolved later.
    # The same class also annotates allow_substs as bool or SomeSubstitutionsType, but Jazzy
    # validates that argument as a bool when the ParameterFile object is constructed. Because of
    # that runtime validation, params_file_allow_substs must be evaluated before it is passed as
    # allow_substs.
    params_file_allow_substs = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('params_file_allow_substs'), bool), bool
    )

    parameters: SomeParameters = [
        ParameterFile(LaunchConfiguration('params_file'), allow_substs=params_file_allow_substs),
        # `expand_gz_topic_names` is always true because Gazebo topics are expected to include the
        # robot namespace so multiple robots can run in the same simulation.
        # `override_frame_id` is set to an empty string because Gazebo plugins publish the required
        # frame_id.
        {
            'use_sim_time': True,
            'config_file': LaunchConfiguration('config_file'),
            'expand_gz_topic_names': True,
            'override_frame_id': '',
        },
        # The bridges for the battery are not configured in the reusable bridge YAML file because
        # the battery plugin does not allow setting the topic name.
        create_battery_bridges(
            model_name=LaunchConfiguration('robot_name').perform(ctx),
            battery_name='main_battery',
            battery_state_ros_topic='main_battery/state',
            battery_recharge_start_ros_topic='main_battery/recharge/start',
            battery_recharge_stop_ros_topic='main_battery/recharge/stop',
        ),
    ]

    return [
        Node(
            package='ros_gz_bridge',
            executable='bridge_node',
            namespace=LaunchConfiguration('robot_namespace'),
            parameters=parameters,
            **rlh.resolve_node_arguments(
                LaunchConfiguration('bridge_node_arguments').perform(ctx),
                default_arguments={'name': 'bridge', 'output': 'screen', 'emulate_tty': True, 'respawn': False},
            ),
        )
    ]
