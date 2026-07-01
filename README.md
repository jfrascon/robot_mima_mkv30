# robot_mima_mkv30

This package models the MiMA MKV30 counterbalance forklift robot for ROS 2 and Gazebo Sim.
It has been tested with Gazebo Sim Harmonic.

Reference manufacturer information for the MKV30 model can be found at:

<https://www.es-forklift.com/3-0-3-5-4-0T-Counterbalance-Forklift-MKV30-35-40-pd719691098.html>

The current modeled variant is `mima_mkv30_sensors1`, which extends the base MKV30 robot with the
sensor set used by the simulation workspace.

![MiMA MKV30 sensors1 model](doc/images/robot_mima_mkv30_sensors1.png)

The package includes:

- URDF/Xacro robot model files.
- Launch files for `robot_state_publisher`.
- ROS-Gazebo bridge configuration for simulation topics.
- Gazebo Sim sensor and system plugin configuration.
- `ros2_control` controller configuration for simulation.
- MiMA-specific `ros2_control` controllers.

## Debugging the sensors1 model

The package includes a local debug launch for checking the robot model in Gazebo Sim before using it
from a larger application launch file. The debug launch starts a simple world, loads the normal robot
launch file, spawns the robot in Gazebo, and opens RViz with a package-local debug configuration.

For the `sensors1` model, call the installed script:

```bash
$(ros2 pkg prefix robot_mima_mkv30)/share/robot_mima_mkv30/scripts/debug_model_sensors1_with_defaults.sh
```

The script passes the default package configuration files for `model_sensors1`:

- `config/model_sensors1/default_params.yaml`
- `config/model_sensors1/default_model_xacro_args.yaml`
- `config/model_sensors1/default_simulation.yaml`

Those defaults are intentional. The script is meant to be a quick way to debug the model with the
known package configuration.

![MiMA MKV30 sensors1 debug launch](doc/images/debug_model_sensors1.png)

The MiMA-specific controllers are not publicly released yet.
