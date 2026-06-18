"""
Helpers to expose public robot models.

The package publishes robot models through files named
`urdf/models/model_<robot_model>.xacro`. The short model name is the part after
`model_`; for example, `model_base.xacro` publishes model `base`.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory

MODEL_FILE_PREFIX = 'model_'


def get_models() -> list[str]:
    """
    Return the public robot models provided by this package.
    """
    urdf_dir = _get_urdf_dir()

    return sorted(
        path.stem.removeprefix(MODEL_FILE_PREFIX)
        for path in urdf_dir.glob(f'{MODEL_FILE_PREFIX}*.xacro')
        if path.is_file()
    )


def _get_urdf_dir() -> Path:
    """
    Return the installed directory that stores public model Xacro files.
    """
    urdf_dir = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('urdf', 'models')

    if not urdf_dir.is_dir():
        raise FileNotFoundError(f'URDF directory {urdf_dir!r} not found.')

    return urdf_dir
