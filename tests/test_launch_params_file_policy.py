import re

from conftest import PACKAGE_DIR


def test_params_file_launch_argument_is_passed_to_parameter_file_as_substitution() -> None:
    resolve_file_pattern = re.compile(
        r"params_file\s*=\s*rlh\.resolve_file\(\s*LaunchConfiguration\('params_file'\)\.perform\(ctx\)\s*\)"
    )
    perform_pattern = re.compile(r"params_file\s*=\s*LaunchConfiguration\('params_file'\)\.perform\(ctx\)")
    is_file_pattern = re.compile(r'Path\(params_file\)\.is_file\(\)')
    offenders = []

    for launch_file in sorted(PACKAGE_DIR.joinpath('launch').glob('*.launch.py')):
        source = launch_file.read_text(encoding='utf-8')

        if resolve_file_pattern.search(source) or perform_pattern.search(source) or is_file_pattern.search(source):
            offenders.append(launch_file.name)

    assert offenders == []
