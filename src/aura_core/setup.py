import os
from glob import glob
from setuptools import setup, find_packages

package_name = 'aura_core'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
         glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ram',
    maintainer_email='ram@example.com',
    description='AURA runtime explainability middleware.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'scenario_manager = aura_core.scenario_manager_node:main',
            'utility_planner = aura_core.utility_planner_node:main',
            'aura_core = aura_core.aura_core_node:main',
            'metrics = aura_core.metrics_node:main',
            'logger = aura_core.logger_node:main',
        ],
    },
)
