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
INSTALL(FILES ${CMAKE_CURRENT_BINARY_DIR}/dnf.1 DESTINATION share/man/man1)
