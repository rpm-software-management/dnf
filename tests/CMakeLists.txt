ADD_TEST(
    NAME test
    COMMAND ${PYTHON_EXECUTABLE} -m unittest discover -s tests -t ${PROJECT_SOURCE_DIR}
    WORKING_DIRECTORY ${PROJECT_SOURCE_DIR})

# For libdnf built with sanitizers, has no effect otherwise.
# dnf tests do some wild stuff and cause a lot of leaks, hence turn leak
# detection off for them.
SET_PROPERTY(TEST test PROPERTY ENVIRONMENT
    "PYTHONPATH=${CMAKE_SOURCE_DIR}/"
    "ASAN_OPTIONS=verify_asan_link_order=0,detect_leaks=0"
)
