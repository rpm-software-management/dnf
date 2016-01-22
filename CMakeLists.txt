PROJECT (dnf NONE)
CMAKE_MINIMUM_REQUIRED (VERSION 2.4)

INCLUDE (${CMAKE_SOURCE_DIR}/VERSION.cmake)

if (NOT PYTHON_DESIRED)
    set (PYTHON_DESIRED "2")
endif()

SET( SYSCONFDIR /etc)
SET( SYSTEMD_DIR /usr/lib/systemd/system)

if (${PYTHON_DESIRED} STREQUAL "2")
	FIND_PACKAGE (PythonInterp REQUIRED)
else()
	SET(Python_ADDITIONAL_VERSIONS 3.3)
	FIND_PACKAGE(PythonLibs 3.0)
	FIND_PACKAGE(PythonInterp 3.0 REQUIRED)
endif()

EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} -c "from sys import stdout; from distutils import sysconfig; stdout.write(sysconfig.get_python_lib())" OUTPUT_VARIABLE PYTHON_INSTALL_DIR)
EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} -c "import sys; sys.stdout.write('%s.%s' % (sys.version_info.major, sys.version_info.minor))" OUTPUT_VARIABLE PYTHON_MAJOR_DOT_MINOR_VERSION)
MESSAGE(STATUS "Python install dir is ${PYTHON_INSTALL_DIR}")

OPTION(USE_CHECKOUT "Configure DNF to work from an out-of-source build" OFF)
if (USE_CHECKOUT AND NOT (${CMAKE_BINARY_DIR} STREQUAL ${CMAKE_SOURCE_DIR}))
    # Out-of-source build with checkout mode enabled
    SET(CHECKOUT_DIR ${CMAKE_SOURCE_DIR})
    # Since nosetests puts the source tree in sys.path[0], make sure an
    # orphaned pyc file (from before the checkout mode was introduced) is not
    # picked up instead
    FILE(REMOVE ${CMAKE_SOURCE_DIR}/dnf/__init__.pyc)
endif()

if (PLUGINPATH)
    # Custom value specified, append it to PYTHONPATH
    if (PYTHONPATH)
        SET(PYTHONPATH ${PYTHONPATH}:)
    endif()
    SET(PYTHONPATH ${PYTHONPATH}${PLUGINPATH})
else()
    # Use the default value
    SET(PLUGINPATH ${PYTHON_INSTALL_DIR}/dnf-plugins)
endif()

ADD_SUBDIRECTORY (dnf)
ADD_SUBDIRECTORY (bin)
ADD_SUBDIRECTORY (etc)
ADD_SUBDIRECTORY (doc)
ADD_SUBDIRECTORY (po)
ENABLE_TESTING()
ADD_SUBDIRECTORY (tests)

CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/bin/dnf.in ${CMAKE_BINARY_DIR}/bin/dnf @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/bin/dnf-automatic.in ${CMAKE_BINARY_DIR}/bin/dnf-automatic @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/dnf/__init__.py.in ${CMAKE_BINARY_DIR}/dnf/__init__.py @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/dnf/const.py.in ${CMAKE_BINARY_DIR}/dnf/const.py @ONLY)
