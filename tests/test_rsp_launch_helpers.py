import importlib.util
from types import ModuleType

from conftest import PACKAGE_DIR


def test_quote_xacro_argument_value_uses_shell_quoting_when_needed() -> None:
    module = _load_rsp_launch_module()

    assert module._quote_xarg_value_if_needed('plain_value') == 'plain_value'
    assert module._quote_xarg_value_if_needed('') == "''"
    assert module._quote_xarg_value_if_needed('value with spaces') == "'value with spaces'"
    assert module._quote_xarg_value_if_needed('value "with quotes"') == '\'value "with quotes"\''


def _load_rsp_launch_module() -> ModuleType:
    module_path = PACKAGE_DIR / 'launch' / '_rsp.launch.py'
    spec = importlib.util.spec_from_file_location('robot_mima_mkv30_rsp_launch', module_path)

    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
