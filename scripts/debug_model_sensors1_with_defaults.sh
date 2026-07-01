#!/usr/bin/env bash
set -euo pipefail

package_share="$(ros2 pkg prefix robot_mima_mkv30)/share/robot_mima_mkv30"

ros2 launch robot_mima_mkv30 debug_robot.launch.py \
    robot_model:=sensors1 \
    robot_name:=mima_mkv30 \
    params_file:="${package_share}/config/model_sensors1/default_params.yaml" \
    params_file_allow_substs:=True \
    model_xacro_args_file:="${package_share}/config/model_sensors1/default_model_xacro_args.yaml" \
    sim_file:="${package_share}/config/model_sensors1/default_simulation.yaml" \
    use_rviz:=True \
    use_gz_gui:=True
