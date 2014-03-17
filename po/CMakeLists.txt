# pushing/pulling translations to transifex
ADD_CUSTOM_TARGET (gettext-export
                   find ${CMAKE_SOURCE_DIR}/../dnf -iname "*.py" |
                   xargs xgettext --from-code=UTF-8 --output=dnf.pot &&
                   tx push -s
                   COMMENT "Pushing translation source file to transifex")
ADD_CUSTOM_TARGET (gettext-update
                   tx pull -f
                   DEPENDS gettext-export
                   COMMENT "Updating translation files from transifex")

FIND_PACKAGE(Gettext)
IF (GETTEXT_FOUND)
    # this process unfortunately reformats .po files so copy them
    FILE(GLOB POS ${CMAKE_SOURCE_DIR}/po/*.po)
    FILE(COPY ${POS} DESTINATION ${CMAKE_BINARY_DIR}/po)
    FILE(GLOB POS_BIN ${CMAKE_BINARY_DIR}/po/*.po)
    GETTEXT_CREATE_TRANSLATIONS(${CMAKE_SOURCE_DIR}/po/dnf.pot ALL ${POS_BIN})
ENDIF()
