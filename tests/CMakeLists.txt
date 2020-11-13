ADD_TEST(test ${PYTHON_EXECUTABLE} -m nose -s ${CMAKE_CURRENT_SOURCE_DIR})

# For libdnf built with sanitizers, has no effect otherwise.
# dnf tests do some wild stuff and cause a lot of leaks, hence turn leak
# detection off for them.
SET_PROPERTY(TEST test PROPERTY ENVIRONMENT "ASAN_OPTIONS=verify_asan_link_order=0,detect_leaks=0")
