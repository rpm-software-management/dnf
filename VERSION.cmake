set (DEFAULT_DNF_VERSION "4.2.22")

if(DEFINED DNF_VERSION)
  if(NOT ${DEFAULT_DNF_VERSION} STREQUAL ${DNF_VERSION})
    message(FATAL_ERROR "Variable DEFAULT_DNF_VERSION=" ${DEFAULT_DNF_VERSION} " in VERSION.cmake differs from Version=" ${DNF_VERSION} " in spec")
  endif()
else()
  set (DNF_VERSION ${DEFAULT_DNF_VERSION})
endif()
