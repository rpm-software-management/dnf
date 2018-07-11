PROJECT (dnf NONE)
CMAKE_MINIMUM_REQUIRED (VERSION 2.4)

INCLUDE (${CMAKE_SOURCE_DIR}/VERSION.cmake)

SET( SYSCONFDIR /etc)
SET( SYSTEMD_DIR /usr/lib/systemd/system)

FIND_PACKAGE (PythonInterp REQUIRED)

EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} -c "from sys import stdout; from distutils import sysconfig; stdout.write(sysconfig.get_python_lib())" OUTPUT_VARIABLE PYTHON_INSTALL_DIR)
EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} -c "import sys; sys.stdout.write(str(sys.version_info.major))" OUTPUT_VARIABLE PYTHON_MAJOR)
MESSAGE(STATUS "Python install dir is ${PYTHON_INSTALL_DIR}")

ADD_SUBDIRECTORY (dnf)
ADD_SUBDIRECTORY (bin)
ADD_SUBDIRECTORY (etc)
ADD_SUBDIRECTORY (doc)
ADD_SUBDIRECTORY (po)
ENABLE_TESTING()
ADD_SUBDIRECTORY (tests)

CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/bin/dnf.in ${CMAKE_SOURCE_DIR}/bin/dnf-${PYTHON_MAJOR} @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/bin/dnf-automatic.in ${CMAKE_SOURCE_DIR}/bin/dnf-automatic-${PYTHON_MAJOR} @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/dnf/const.py.in ${CMAKE_SOURCE_DIR}/dnf/const.py @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/tests/modules/etc/dnf/repos.d/test.repo.in ${CMAKE_SOURCE_DIR}/tests/modules/etc/dnf/repos.d/test.repo @ONLY)
CONFIGURE_FILE(${CMAKE_SOURCE_DIR}/tests/modules/etc/dnf/dnf.conf.in ${CMAKE_SOURCE_DIR}/tests/modules/etc/dnf/dnf.conf @ONLY)
