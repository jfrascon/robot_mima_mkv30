from pathlib import Path

import yaml
from conftest import PACKAGE_DIR


def test_default_bridge_configs_use_explicit_ros_and_gazebo_topic_names() -> None:
    for bridge_file in _default_bridge_files():
        bridges = yaml.safe_load(bridge_file.read_text(encoding='utf-8'))

        assert isinstance(bridges, list), bridge_file

        for bridge in bridges:
            assert isinstance(bridge, dict), bridge_file
            assert 'topic_name' not in bridge, bridge_file
            assert isinstance(bridge.get('ros_topic_name'), str), bridge_file
            assert isinstance(bridge.get('gz_topic_name'), str), bridge_file


def _default_bridge_files() -> list[Path]:
    return sorted(PACKAGE_DIR.glob('config/model_*/default_bridge.yaml'))
