# robot_mima_mkv30

This package provides Xacro models, ROS 2 launch files, and simulation configuration for robots inspired by the MiMA MKV30 counterbalance forklift.

The package is prepared to support several robot models derived from the same MKV30 base. The current models are:

- `base`: basic MKV30-inspired robot model.
- `sensors1`: model based on `base`, with additional sensors placed in a specific layout.

Reference manufacturer information for the MKV30 model can be found at:

<https://www.es-forklift.com/3-0-3-5-4-0T-Counterbalance-Forklift-MKV30-35-40-pd719691098.html>

![MiMA MKV30 sensors1 model](doc/images/robot_mima_mkv30_sensors1.png)

## What Is Included

The package includes:

- Xacro robot files.
- Per-model configuration under `config/model_*`.
- Real robot launch preset: `launch/real_robot.launch.py`.
- Local debug launch file: `launch/debug_robot.launch.py`.
- Bridge, simulation, RViz, and `ros2_control` configuration.

## Normal Use

Launch the real robot preset with:

```bash
ros2 launch robot_mima_mkv30 real_robot.launch.py ...
```

The most relevant launch arguments are:

- `robot_model`: selects the model to launch, for example `base` or `sensors1`.
- `robot_name`: sets the robot name used by the launch file.
- `robot_params_file`: selects the complete ROS parameter file.
- `robot_params_file_allow_substs`: enables or disables substitutions inside the parameter file.
- `robot_xacro_args_file`: selects the file with Xacro arguments for the robot.

`real_robot.launch.py` does not launch Gazebo bridge nodes and does not load simulation plugins.
Gazebo simulation and rosbag replay launch files should compose the internal launch files they need.

## Real, Simulation, And Bag Replay Launching

`real_robot.launch.py` is intentionally a real-robot preset. It launches the parts that belong to the robot when the robot is running outside Gazebo: `robot_state_publisher`, the local `ros2_control` controller manager, and the controller spawners. It does not accept a simulation Xacro file, does not load Gazebo plugins, does not launch bridge nodes, and does not use ROS time from `/clock`. This makes the launch file easier to reason about: if this preset is used, the robot is expected to be controlled as a real robot, not as a Gazebo model.

Gazebo simulation needs a different launch structure because the order matters. A simulation launcher should usually compose the internal launch files in this order:

1. Launch `robot_state_publisher`, so the robot description is available.
2. Spawn the model in Gazebo, so the Gazebo plugins from the simulation Xacro file are actually loaded.
3. Launch the Gazebo bridge, because there are Gazebo topics to bridge only after the model and its plugins exist.
4. Launch the `ros2_control` controller spawners. In simulation, the controller manager is normally provided by the Gazebo `ros2_control` plugin loaded with the model, so the standalone `ros2_control_node` should not be started by the robot package.

`debug_robot.launch.py` is the package-local example of that simulation composition. Project-level launch files can follow the same idea and include only the pieces they need.

Rosbag replay is a third case. A bag may already contain sensor topics, transforms, and other runtime data, so replay launch files should be explicit about which parts they still need. In many replay sessions there is no Gazebo model to spawn, no Gazebo bridge to launch, and no controller manager or controllers to start.

## Model Configuration

Each model has its own package-maintained configuration under `config/model_<name>`.

For `sensors1`, the main default files are:

- `config/model_sensors1/default_params.yaml`
- `config/model_sensors1/default_xacro_args.yaml`
- `config/model_sensors1/default_simulation.yaml`
- `config/model_sensors1/default_bridge.yaml`

These files are not generic examples. They are the default configuration maintained by this package
for the `sensors1` model.

A user can add another model, for example `sensors2`, by adding the required Xacro files,
configuration files, and package wiring needed to expose that model.

## Debugging The sensors1 Model

The package includes a quick debug flow for checking the `sensors1` model in Gazebo Sim and RViz.

Call the installed script:

```bash
$(ros2 pkg prefix robot_mima_mkv30)/share/robot_mima_mkv30/scripts/debug_model_sensors1_with_defaults.sh
```

The script uses the package defaults from `model_sensors1`. It is meant to run the known package
configuration without having to pass the default files by hand.

![MiMA MKV30 sensors1 debug launch](doc/images/debug_model_sensors1.png)

## Notes

The MiMA-specific controllers are not publicly released yet.
