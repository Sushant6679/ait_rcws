cmake_minimum_required(VERSION 3.10)
project(TinyFramePython C)

# Explicitly set generator if not specified
if(NOT DEFINED CMAKE_GENERATOR)
    set(CMAKE_GENERATOR "MinGW Makefiles" CACHE INTERNAL "Generator used")
endif()

# Set C standard
set(CMAKE_C_STANDARD 99)
set(CMAKE_C_STANDARD_REQUIRED ON)

# Set output directory
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)

# Create shared library
add_library(tinyframe_python SHARED
    tinyframe_wrapper.c
    TinyFrame.c
)

# Include directories
target_include_directories(tinyframe_python PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}
)

# Create proper extensions for different platforms
if(WIN32)
    set_target_properties(tinyframe_python PROPERTIES
        PREFIX ""
        OUTPUT_NAME "tinyframe_python"
        SUFFIX ".dll"
    )
else()
    set_target_properties(tinyframe_python PROPERTIES
        PREFIX "lib"
        OUTPUT_NAME "tinyframe_python"
        SUFFIX ".so"
    )
endif()

# Define export symbol for Windows DLL
if(WIN32)
    target_compile_definitions(tinyframe_python PRIVATE -DBUILD_DLL)
endif()

# Install targets
install(TARGETS tinyframe_python
    LIBRARY DESTINATION lib
    RUNTIME DESTINATION bin
)