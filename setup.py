from setuptools import setup
from pathlib import Path

with open("docs/README.md", "r") as readme:
    long_description = readme.read()

compiled_path = Path.home() / '.pyxbld' / 'lib.win-amd64-3.7' / 'libyaz0' /\
                'yaz0_cy.cp37-win_amd64.pyd'
if not compiled_path.exists():
    compiled_path.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(Path() / 'bcml' / 'data' / 'yaz0_cy.cp37-win_amd64.pyd', compiled_path)

setup(
    name='bcml',
    version='2.5.1',
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
        'cython>=0.29.13',
        'libyaz0>=0.5',
        'PySide2>=5.13.0',
        'pyYaml>=5.1.1',
        'sarc>=2.0.1',
        'rstb>=1.1.2',
        #'wszst-yaz0>=1.2.0.post1',
        'xxhash>=1.3.0'
    ]
)
