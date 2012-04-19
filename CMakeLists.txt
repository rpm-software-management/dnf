PROJECT (dnf)
CMAKE_MINIMUM_REQUIRED (VERSION 2.4)

FIND_PACKAGE (PythonInterp REQUIRED)
EXECUTE_PROCESS(COMMAND ${PYTHON_EXECUTABLE} -c "from sys import stdout; from distutils import sysconfig; stdout.write(sysconfig.get_python_lib())" OUTPUT_VARIABLE PYTHON_INSTALL_DIR)
MESSAGE(STATUS "Python install dir is ${PYTHON_INSTALL_DIR}")

ADD_SUBDIRECTORY (dnf)
ADD_SUBDIRECTORY (bin)
ENABLE_TESTING()
ADD_SUBDIRECTORY (tests)
