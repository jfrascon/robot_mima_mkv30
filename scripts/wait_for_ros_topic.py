#!/usr/bin/env python3
"""
Wait until one ROS topic appears in the ROS graph.

The simulation debug launch uses this script before inserting the robot in Gazebo. The robot
must publish `robot_description` first, because `ros_gz_sim create` reads the model from that
topic.
"""

import argparse
import sys
import time

import rclpy
from rclpy.node import Node


def main() -> int:
    """
    Wait for the requested topic and return a process exit code.

    The script returns `0` when the topic appears. It returns `1` when the timeout expires. Launch
    uses that exit code to decide whether it can run the next action.
    """
    args = _parse_args()
    start_time = time.monotonic()

    rclpy.init(args=None)
    node = rclpy.create_node('wait_for_ros_topic')

    print(f"wait_for_ros_topic.py: waiting for ROS topic '{args.topic_name}'", flush=True)

    try:
        while True:
            rclpy.spin_once(node, timeout_sec=0.0)

            if _topic_exists(node, args.topic_name):
                elapsed_time = time.monotonic() - start_time
                print(
                    f"wait_for_ros_topic.py: topic '{args.topic_name}' appeared after {elapsed_time:.2f} s", flush=True
                )
                return 0

            elapsed_time = time.monotonic() - start_time

            if elapsed_time >= args.timeout:
                print(
                    f"wait_for_ros_topic.py: timed out after {elapsed_time:.2f} s waiting for '{args.topic_name}'",
                    file=sys.stderr,
                    flush=True,
                )
                return 1

            time.sleep(args.poll_period)
    finally:
        node.destroy_node()
        rclpy.shutdown()


def _parse_args() -> argparse.Namespace:
    """Parse the topic name and timing options used by the launch file."""
    parser = argparse.ArgumentParser(description='Wait until one ROS topic appears in the ROS graph.')
    parser.add_argument('topic_name', help='Fully qualified ROS topic name to wait for')
    parser.add_argument('--timeout', type=float, default=60.0, help='Maximum wait time in seconds')
    parser.add_argument('--poll-period', type=float, default=0.25, help='Seconds between graph checks')
    return parser.parse_args()


def _topic_exists(node: Node, topic_name: str) -> bool:
    """Return `True` when the requested topic currently exists in the ROS graph."""
    return any(name == topic_name for name, _ in node.get_topic_names_and_types())


if __name__ == '__main__':
    raise SystemExit(main())
