import setuptools
import re

with open('cmyui/__init__.py', 'r') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]', f.read(), re.MULTILINE).group(1)

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name = 'cmyui',
    author = 'cmyui',
    url = 'https://github.com/cmyui/cmyui_pkg',
    version = version,
    packages = setuptools.find_packages(),
    description = 'Tools I find myself constantly rebuilding and reusing.',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    license = 'MIT',
    install_requires = [ # pretty triggered this is doubled
        'aiohttp',
        'aiomysql',
        'mysql-connector-python',
        'orjson'
    ],
    python_requires = '>=3.9',
    package_data = {
        'cmyui': ['py.typed'],
    },
    classifiers = [
        'Programming Language :: Python :: 3.9',
        'License :: OSI Approved :: MIT License',
    ]
)
