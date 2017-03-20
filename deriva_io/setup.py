#
# Copyright 2017 University of Southern California
# Distributed under the Apache License, Version 2.0. See LICENSE for more info.
#

""" Installation script for the deriva_io module.
"""

from setuptools import setup, find_packages

setup(
    name="deriva_io",
    description="IO modules for Python-based DERIVA platform code",
    url='https://github.com/informatics-isi-edu/deriva-py/deriva_io',
    maintainer='USC Information Sciences Institute ISR Division',
    maintainer_email='misd-support@isi.edu',
    version="0.1.0",
    packages=find_packages(),
    package_data={},
    test_suite='test',
    requires=[
        'argparse',
        'os',
        'sys',
        'logging',
        're',
        'scandir'],
    license='Apache 2.0',
    classifiers=[
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5'
    ]
)

