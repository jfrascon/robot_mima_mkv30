"""
Helpers to expose public robot models and their launch-facing Xacro arguments.

The package publishes robot models through files named
`urdf/models/model_<robot_model>.xacro`. The short model name is the part after
`model_`; for example, `model_base.xacro` publishes model `base`.

The xargs YAML files are the launch-facing contract. They list the `xacro:arg`
values that callers may override through launch arguments. Fixed dimensions of
this concrete robot model are not xargs; they stay as Xacro properties inside
the model includes.
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import ros2_launch_helpers as rlh
import yaml
from ament_index_python.packages import get_package_share_directory
from launch.actions import DeclareLaunchArgument, SetLaunchConfiguration
from launch.launch_context import LaunchContext
from launch.substitutions import LaunchConfiguration
from launch.utilities.type_utils import normalize_typed_substitution, perform_typed_substitution

from launch import LaunchDescriptionEntity

MODEL_FILE_PREFIX = 'model_'


def declare_launch_arguments(robot_model: str) -> List[LaunchDescriptionEntity]:
    """
    Return launch argument declarations for one public robot model.
    """
    ldes: List[LaunchDescriptionEntity] = []

    for xarg_name, xarg_cfg in _get_xargs(robot_model).items():
        kwargs = {'default_value': xarg_cfg['default_value'], 'description': xarg_cfg['description']}

        if 'choices' in xarg_cfg:
            kwargs['choices'] = xarg_cfg['choices']

        ldes.append(DeclareLaunchArgument(xarg_name, **kwargs))

    return ldes


def get_launch_configuration_entries(robot_model: str) -> Dict[str, LaunchConfiguration]:
    """
    Return launch substitution entries for the xargs of one robot model.
    """
    return {xarg_name: LaunchConfiguration(xarg_name) for xarg_name in _get_xargs(robot_model).keys()}


def get_model_launch_filename(robot_model: str) -> str:
    """
    Return the public launch filename for one short robot model name.
    """
    return f'{MODEL_FILE_PREFIX}{robot_model}.launch.py'


def get_model_xacro_filename(robot_model: str) -> str:
    """
    Return the public Xacro filename for one short robot model name.
    """
    return f'{MODEL_FILE_PREFIX}{robot_model}.xacro'


def get_models() -> List[str]:
    """
    Return the public robot models provided by this package.
    """
    urdf_dir = _get_urdf_dir()

    return sorted(
        path.stem.removeprefix(MODEL_FILE_PREFIX)
        for path in urdf_dir.glob(f'{MODEL_FILE_PREFIX}*.xacro')
        if path.is_file()
    )


def get_models_with_xargs() -> List[str]:
    """
    Return the public robot models that have xargs YAML files.
    """
    return [robot_model for robot_model in get_models() if model_has_xargs(robot_model)]


def get_xarg_names(robot_model: str) -> List[str]:
    """
    Return xarg names for the requested robot model.
    """
    return list(_get_xargs(robot_model).keys())


def model_exists(robot_model: str) -> bool:
    """
    Return whether one public robot model exists.
    """
    robot_model = (robot_model or '').strip()

    if not robot_model:
        return False

    return robot_model in get_models()


def model_has_xargs(robot_model: str) -> bool:
    """
    Return whether one public robot model has a xargs YAML file.
    """
    robot_model = (robot_model or '').strip()

    if not model_exists(robot_model):
        return False

    return _xargs_file_exists(robot_model)


def process_controller_config_file(ctx: LaunchContext) -> List[LaunchDescriptionEntity]:
    """
    Prepare the final controller YAML file for the current robot instance.

    The input `controller_config_file` may be a plain YAML file or a template
    that contains supported tokens such as `@robot_prefix@`. The output is
    always written to `/tmp/<robot_namespace>_controllers.yaml`, and the launch
    context key `controller_config_file` is updated to point to that final file.
    """
    controller_config_file = LaunchConfiguration('controller_config_file').perform(ctx)

    if not controller_config_file:
        raise RuntimeError('controller_config_file is required to prepare the controller YAML file.')

    source_path = Path(rlh.resolve_file(controller_config_file))

    if not source_path.is_file():
        raise FileNotFoundError(f"Controller config file '{controller_config_file}' does not exist.")

    robot_namespace = LaunchConfiguration('namespace').perform(ctx)
    robot_prefix = LaunchConfiguration('robot_prefix').perform(ctx)

    if not robot_namespace:
        raise RuntimeError("Launch context key 'namespace' must not be empty.")

    if not robot_prefix:
        raise RuntimeError("Launch context key 'robot_prefix' must not be empty.")

    use_sim_time = perform_typed_substitution(
        ctx, normalize_typed_substitution(LaunchConfiguration('use_sim_time'), bool), bool
    )
    use_sim_time_yaml = str(use_sim_time).lower()

    rendered_text = source_path.read_text(encoding='utf-8')
    rendered_text = rendered_text.replace('@robot_prefix@', robot_prefix)
    rendered_text = rendered_text.replace('@robot_namespace@', robot_namespace)
    rendered_text = rendered_text.replace('@use_sim_time@', use_sim_time_yaml)

    unknown_tokens = sorted(set(re.findall(r'@[A-Za-z0-9_]+@', rendered_text)))

    if unknown_tokens:
        raise RuntimeError(f'Unknown controller config template tokens: {unknown_tokens}')

    output_name = rlh.flatten_namespace(robot_namespace, '_') or 'robot'
    output_path = Path('/tmp') / f'{output_name}_controllers.yaml'
    output_path.write_text(rendered_text, encoding='utf-8')

    return [SetLaunchConfiguration('controller_config_file', str(output_path))]


def _check_xarg_fields(xarg_name: str, xarg_cfg: Dict[str, Any], xargs_file: Path) -> None:
    """
    Validate schema fields for one xarg entry.
    """
    required_xarg_fields = {'default_value', 'description'}
    optional_xarg_fields = {'choices'}
    allowed_fields = required_xarg_fields.union(optional_xarg_fields)
    present_fields = set(xarg_cfg.keys())

    unknown_fields = present_fields.difference(allowed_fields)

    if unknown_fields:
        raise ValueError(
            f'Xarg {xarg_name!r} in file {xargs_file!r} has fields that are not allowed: '
            f'{sorted(unknown_fields)}. Allowed fields: {sorted(allowed_fields)}.'
        )

    missing_fields = required_xarg_fields.difference(present_fields)

    if missing_fields:
        raise ValueError(
            f'Xarg {xarg_name!r} in file {xargs_file!r} is missing required fields: {sorted(missing_fields)}.'
        )

    for field_name, field_value in xarg_cfg.items():
        if field_name == 'choices':
            if not isinstance(field_value, list) or not all(isinstance(choice, str) for choice in field_value):
                raise ValueError(
                    f"Field 'choices' for xarg {xarg_name!r} in file {xargs_file!r} must be a list of strings."
                )
        elif not isinstance(field_value, str):
            raise ValueError(f'Field {field_name!r} for xarg {xarg_name!r} in file {xargs_file!r} must be a string.')


def _get_model_xargs_filename(robot_model: str) -> str:
    """
    Return the internal xargs YAML filename for one short robot model name.
    """
    return f'{MODEL_FILE_PREFIX}{robot_model}.yaml'


def _get_urdf_dir() -> Path:
    """
    Return the installed directory that stores public model Xacro files.
    """
    urdf_dir = Path(get_package_share_directory('robot_mima_mkv30')).joinpath('urdf', 'models')

    if not urdf_dir.is_dir():
        raise FileNotFoundError(f'URDF directory {urdf_dir!r} not found.')

    return urdf_dir


def _get_xargs(robot_model: str) -> Dict[str, Dict[str, Any]]:
    """
    Return the internal xargs mapping for the requested robot model.
    """
    robot_model = (robot_model or '').strip()

    if not model_has_xargs(robot_model):
        return {}

    model_xargs_file = _get_model_xargs_filename(robot_model)
    return _load_xargs_yaml(model_xargs_file)


def _get_xargs_dir() -> Path:
    """
    Return the directory that stores internal xargs YAML files.
    """
    xargs_dir = Path(__file__).resolve().parent.joinpath('xargs')

    if not xargs_dir.is_dir():
        raise FileNotFoundError(f'Xargs directory {xargs_dir!r} not found.')

    return xargs_dir


def _load_xargs_yaml(xargs_file: str) -> Dict[str, Dict[str, Any]]:
    """
    Load xargs directly from one internal YAML filename.
    """
    xargs_file_path = _get_xargs_dir().joinpath(xargs_file)

    if not xargs_file_path.is_file():
        raise FileNotFoundError(f'Xargs file {xargs_file_path!r} not found.')

    with xargs_file_path.open('r', encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError(f'Xargs file {xargs_file_path!r} must contain a mapping.')

    for xarg_name, xarg_cfg in data.items():
        if not isinstance(xarg_name, str):
            raise ValueError(f'Xarg name {xarg_name!r} in file {xargs_file_path!r} must be a string.')
        if not isinstance(xarg_cfg, dict):
            raise ValueError(f'Xarg {xarg_name!r} in file {xargs_file_path!r} must contain a mapping.')

        _check_xarg_fields(xarg_name, xarg_cfg, xargs_file_path)

    return data


def _xargs_file_exists(robot_model: str) -> bool:
    """
    Return whether the xargs YAML file for one model exists.
    """
    return _get_xargs_dir().joinpath(_get_model_xargs_filename(robot_model)).is_file()
