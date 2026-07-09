import importlib.util
from types import ModuleType

from conftest import PACKAGE_DIR


def test_bridge_launch_uses_shared_battery_bridge_configuration() -> None:
    module = _load_bridge_launch_module()

    assert not hasattr(module, '_load_battery_bridge_params')
    assert module.create_battery_bridges.__module__ == 'robotics_description.bridge_configurations'


def _load_bridge_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_ros_gz_bridge.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_bridge_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
