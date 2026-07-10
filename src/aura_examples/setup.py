from setuptools import setup

package_name = 'aura_examples'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Ram',
    maintainer_email='ram@example.com',
    description='Example AURA-compatible planners.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'rule_planner = aura_examples.rule_planner_node:main',
        ],
    },
)
