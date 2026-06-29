#!/usr/bin/env python3
"""
TinyFrame Python Package Setup
"""

import os
import sys
import platform
import subprocess
from setuptools import setup, find_packages, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.install import install
from setuptools.command.develop import develop


class CMakeBuild(build_ext):
    """Build the C library using CMake"""
    
    def run(self):
        # Check if CMake is installed
        try:
            subprocess.check_output(['cmake', '--version'])
        except OSError:
            raise RuntimeError(
                "CMake must be installed to build the TinyFrame library"
            )
        
        # Build the C library
        for ext in self.extensions:
            self.build_cmake(ext)
    
    def build_cmake(self, ext):
        # Get the directory where the C library should be built
        build_temp = os.path.join(self.build_temp, os.path.dirname(
            self.get_ext_fullpath(ext.name)))
        
        # Make sure the build directory exists
        os.makedirs(build_temp, exist_ok=True)
        
        # Get the source directory
        source_dir = os.path.abspath(os.path.dirname(__file__))
        
        # Configure and build the C library
        cfg = 'Debug' if self.debug else 'Release'
        cmake_args = [
            f'-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={build_temp}',
            f'-DCMAKE_BUILD_TYPE={cfg}',
            '-DCMAKE_POSITION_INDEPENDENT_CODE=ON',
        ]
        
        # Add platform-specific arguments
        if platform.system() == "Windows":
            cmake_args += [
                '-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_{}={}'.format(
                    cfg.upper(), build_temp
                )
            ]
            if sys.maxsize > 2**32:
                cmake_args += ['-A', 'x64']
        
        # Run CMake to configure the build
        subprocess.check_call(
            ['cmake', source_dir] + cmake_args,
            cwd=build_temp
        )
        
        # Build the library
        subprocess.check_call(
            ['cmake', '--build', '.', '--config', cfg],
            cwd=build_temp
        )
        
        # Copy the library to the package directory
        install_dir = os.path.dirname(self.get_ext_fullpath(ext.name))
        
        # Determine the library filename based on platform
        if platform.system() == "Windows":
            lib_name = 'tinyframe_python.dll'
            build_lib_dir = os.path.join(build_temp, cfg)
        else:
            if platform.system() == "Darwin":  # macOS
                lib_name = 'libtinyframe_python.dylib'
            else:  # Linux and others
                lib_name = 'libtinyframe_python.so'
            build_lib_dir = build_temp
        
        # Ensure the destination directory exists
        os.makedirs(install_dir, exist_ok=True)
        
        # Copy the library file
        lib_path = os.path.join(build_lib_dir, lib_name)
        if os.path.exists(lib_path):
            # Copy to package directory
            dest_path = os.path.join(install_dir, lib_name)
            self.copy_file(lib_path, dest_path)
        else:
            raise RuntimeError(f"Library file not found: {lib_path}")


class InstallCommand(install):
    """Custom install command that builds the C library first"""
    def run(self):
        self.run_command('build_ext')
        install.run(self)


class DevelopCommand(develop):
    """Custom develop command that builds the C library first"""
    def run(self):
        self.run_command('build_ext')
        develop.run(self)


setup(
    name="tinyframe",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Python wrapper for the TinyFrame protocol library",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/tinyframe-python",
    packages=find_packages(),
    ext_modules=[
        Extension(
            name="tinyframe._tinyframe",
            sources=[]  # No sources here, we'll build with CMake
        )
    ],
    cmdclass={
        'build_ext': CMakeBuild,
        'install': InstallCommand,
        'develop': DevelopCommand,
    },
    install_requires=[
        'pyserial',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)