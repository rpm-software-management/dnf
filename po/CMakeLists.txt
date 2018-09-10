# pushing/pulling translations to zanata

file (RELATIVE_PATH SRCDIR ${CMAKE_CURRENT_SOURCE_DIR} ${CMAKE_SOURCE_DIR}/dnf)
ADD_CUSTOM_TARGET (gettext-export
                   find ${SRCDIR} -iname "*.py" |
                   xargs xgettext --from-code=UTF-8 --keyword=P_:1,2 --keyword=C_:1c,2 -c --output=dnf.pot &&
                   zanata push -f
                   WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                   COMMENT "Pushing translation source file to zanata")
ADD_CUSTOM_TARGET (gettext-update
                   zanata pull
                   WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                   COMMENT "Updating translation files from zanata")

FIND_PACKAGE(Gettext)
IF (GETTEXT_FOUND)
    # this process unfortunately reformats .po files so copy them
    FILE(GLOB POS ${CMAKE_CURRENT_SOURCE_DIR}/*.po)
    FILE(COPY ${POS} DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
    FILE(GLOB POS_BIN ${CMAKE_CURRENT_BINARY_DIR}/*.po)
    GETTEXT_CREATE_TRANSLATIONS(${CMAKE_CURRENT_SOURCE_DIR}/dnf.pot ALL ${POS_BIN})
ENDIF()
