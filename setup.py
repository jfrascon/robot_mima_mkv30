import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'robot_mima_mkv30'


def _glob_files(pattern):
    """Return only regular files for a glob pattern."""
    return [path for path in glob(pattern) if os.path.isfile(path)]


def _walk_data_files(source_root, install_root):
    """Return data_files entries for all regular files under one source tree."""
    data_files = []

    for current_root, _, filenames in os.walk(source_root):
        if not filenames:
            continue

        relative_dir = os.path.relpath(current_root, source_root)
        install_dir = install_root if relative_dir == '.' else os.path.join(install_root, relative_dir)
        files = [os.path.join(current_root, filename) for filename in sorted(filenames)]
        data_files.append((install_dir, files))

    return data_files


setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test', 'tests']),
    package_data={package_name: ['xargs/*.yaml']},
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{package_name}']),
        (f'share/{package_name}', ['package.xml']),
        (f'share/{package_name}/launch', _glob_files('launch/*')),
        (f'share/{package_name}/urdf/models', _glob_files('urdf/models/*')),
        (f'share/{package_name}/urdf/includes', _glob_files('urdf/includes/*')),
        (f'share/{package_name}/config/model_base', _glob_files('config/model_base/*')),
        (f'share/{package_name}/config/model_sensors1', _glob_files('config/model_sensors1/*')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    zip_safe=True,
    maintainer='Juan Francisco Rascon Crespo',
    maintainer_email='jfrascon@me.com',
    description='URDF description for the MiMA MKV30 base model',
    license='Apache-2.0',
    extras_require={'test': ['pytest']},
    python_requires='>=3.8',
)
