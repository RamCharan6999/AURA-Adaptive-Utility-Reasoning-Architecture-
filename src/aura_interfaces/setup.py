from setuptools import setup

package_name = 'aura_interfaces'

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
    description='The AURA middleware contract.',
    license='MIT',
    entry_points={'console_scripts': []},
)
