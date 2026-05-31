# robot_mima_mkv30

This package models the MiMA MKV30 counterbalance forklift robot for ROS 2 and Gazebo Sim.
It has been tested with Gazebo Sim Harmonic.

The current modeled variant is `mima_mkv30_sensors1`, which extends the base MKV30 robot with the
sensor set used by the simulation workspace.

![MiMA MKV30 sensors1 model](doc/images/robot_mima_mkv30_sensors1.png)

Reference manufacturer information for the MKV30 model can be found at:

<https://www.es-forklift.com/3-0-3-5-4-0T-Counterbalance-Forklift-MKV30-35-40-pd719691098.html>

The package includes:

- URDF/Xacro robot model files.
- Launch files for `robot_state_publisher`.
- ROS-Gazebo bridge configuration for simulation topics.
- Gazebo Sim sensor and system plugin configuration.
- `ros2_control` controller configuration for simulation.
- MiMA-specific `ros2_control` controllers.

The MiMA-specific controllers are not publicly released yet.
