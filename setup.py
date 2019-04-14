from setuptools import setup

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

setup(
    name='bcml',
    version='0.993',
    author='NiceneNerd',
    author_email='macadamiadaze@gmail.com',
    description='A mod manager for The Legend of Zelda: Breath of the Wild on Cemu',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/NiceneNerd/BCML',
    include_package_data=True,
    packages=['bcml'],
    entry_points={
        'console_scripts': [
            'bcml = bcml.__init__:main'
        ],
        'gui_scripts': [
            'bcml-gui = bcml.gui:main'
        ]
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3 :: Only'
    ],
    python_requires='>=3.6',
    install_requires=[
        'sarc',
        'rstb',
        'patool',
        'wszst_yaz0',
        'wxPython',
        'xxhash'
    ]
)