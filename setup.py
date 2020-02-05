from setuptools import setup
from pathlib import Path

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

from bcml.__version__ import VERSION

setup(
    name='bcml',
    version=VERSION,
    author='NiceneNerd',
    author_email='macadamiadaze@gmail.com',
    description='A mod manager for The Legend of Zelda: Breath of the Wild on Cemu',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/NiceneNerd/BCML',
    include_package_data=True,
    packages=['bcml'],
    entry_points={
        'gui_scripts': [
            'bcml = bcml.__init__:main'
        ],
        'console_scripts': [
            'bcml-debug = bcml.__init__:main'
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3 :: Only'
    ],
    python_requires='>=3.6',
    install_requires=[
        'aamp>=1.4.1',
        'byml>=2.3.1',
        'syaz0>=1.0.1',
        'PySide2>=5.14.1',
        'pyYaml>=5.3',
        'sarc>=2.0.3',
        'rstb>=1.1.3',
        'xxhash>=1.4.3'
    ]
)
