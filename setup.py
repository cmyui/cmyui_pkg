import setuptools

with open('README.md', 'r') as f:
    long_description = f.read()

setuptools.setup(
    name = 'cmyui',
    version = '1.5.8',
    author = 'cmyui',
    author_email = 'cmyuiosu@gmail.com',
    description = 'Some generic tools I find myself using often (web, mysql/pg, logging, utils, etc).',
    long_description = long_description,
    long_description_content_type = 'text/markdown',
    url = 'https://github.com/cmyui/cmyui_pkg',
    packages = setuptools.find_packages(),
    classifiers = [
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires = '>=3.9',
    package_data = {
        'cmyui': ['py.typed'],
    }
)
