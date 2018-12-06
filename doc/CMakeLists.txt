# html and man documentation are separate targets, apparently there's no way to
# tell sphinx-build to do them both in one go:
ADD_CUSTOM_TARGET (doc-html
          PYTHONPATH=${CMAKE_SOURCE_DIR} sphinx-build -b html
          ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR}
          COMMENT "Building html documentation")
ADD_CUSTOM_TARGET (doc-man
          PYTHONPATH=${CMAKE_SOURCE_DIR} sphinx-build -b man
          ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_CURRENT_BINARY_DIR}
          COMMENT "Building manpage documentation")
ADD_CUSTOM_TARGET (doc)
ADD_DEPENDENCIES (doc doc-html doc-man)

if (NOT WITH_MAN EQUAL 0)
    INSTALL(FILES ${CMAKE_CURRENT_BINARY_DIR}/dnf.8
              ${CMAKE_CURRENT_BINARY_DIR}/dnf.automatic.8
              ${CMAKE_CURRENT_BINARY_DIR}/yum2dnf.8
              ${CMAKE_CURRENT_BINARY_DIR}/yum.8
              ${CMAKE_CURRENT_BINARY_DIR}/yum-shell.8
              DESTINATION share/man/man8)
    INSTALL(FILES ${CMAKE_CURRENT_BINARY_DIR}/dnf.conf.5
              ${CMAKE_CURRENT_BINARY_DIR}/yum.conf.5
              DESTINATION share/man/man5)
    INSTALL(FILES ${CMAKE_CURRENT_BINARY_DIR}/yum-aliases.1
              DESTINATION share/man/man1)
endif()
