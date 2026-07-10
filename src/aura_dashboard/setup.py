import os
from glob import glob
from setuptools import setup

package_name = 'aura_dashboard'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'operator_console'),
         glob('operator_console/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ram',
    maintainer_email='ram@example.com',
    description='AURA operator console and CLI.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'web_bridge = aura_dashboard.web_bridge_node:main',
            'aura_cli = aura_dashboard.aura_cli:main',
        ],
    },
)
