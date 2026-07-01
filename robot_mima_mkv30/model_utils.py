from pathlib import Path

from ament_index_python.packages import get_package_share_directory


def get_models() -> list[str]:
    """
    Return the public robot model names available in this package.

    Public model xacro files are stored as `urdf/models/model_<robot_model>.xacro`.
    The launch argument uses the short model name, for example `base` or `sensors1`.
    """
    model_file_prefix = 'model_'
    urdf_dir = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('urdf', 'models')

    if not urdf_dir.is_dir():
        raise FileNotFoundError(f'URDF directory {urdf_dir!r} does not exist.')

    return sorted(
        path.stem.removeprefix(model_file_prefix)
        for path in urdf_dir.glob(f'{model_file_prefix}*.xacro')
        if path.is_file()
    )
