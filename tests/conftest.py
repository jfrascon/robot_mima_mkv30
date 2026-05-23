import os
import subprocess
import sys
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_DIR))
sys.path.insert(0, str(PACKAGE_DIR.parent / 'ros2_launch_helpers'))


def workspace_dir() -> Path:
    """Return the workspace root that contains install/setup.bash."""
    for parent in PACKAGE_DIR.parents:
        if parent.joinpath('install', 'setup.bash').is_file():
            return parent

    raise FileNotFoundError('Could not locate workspace root with install/setup.bash')


WORKSPACE_DIR = workspace_dir()
install_prefix = str(WORKSPACE_DIR / 'install')
current_ament_prefix_path = os.environ.get('AMENT_PREFIX_PATH', '')
os.environ['AMENT_PREFIX_PATH'] = (
    install_prefix if not current_ament_prefix_path else f'{install_prefix}:{current_ament_prefix_path}'
)


def run_bash(command: str, *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run one bash command in the workspace with ROS and workspace setup sourced."""
    ros_distro = os.environ.get('ROS_DISTRO', 'jazzy')
    ros_setup = os.environ.get('ROS_SETUP_BASH', f'/opt/ros/{ros_distro}/setup.bash')
    bash_command = f'source "{ros_setup}" && source "{WORKSPACE_DIR / "install" / "setup.bash"}" && {command}'

    return subprocess.run(
        ['bash', '-lc', bash_command], cwd=WORKSPACE_DIR, text=True, capture_output=True, timeout=timeout, check=False
    )
