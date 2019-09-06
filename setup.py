from setuptools import setup

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

setup(
    name='bcml',
    version='2.3.0-beta1',
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
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 3 :: Only'
    ],
    python_requires='>=3.7',
    install_requires=[
        'aamp>=1.3.0.post1',
        'byml>=2.3.0.post1',
        'PySide2>=5.13.0',
        'pyYaml>=5.1.1',
        'sarc>=2.0.1',
        'rstb>=1.1.2',
        'wszst-yaz0>=1.2.0.post1',
        'xxhash>=1.3.0'
    ]
)
