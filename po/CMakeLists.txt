# pushing/pulling translations to transifex

SET(SRC_PO ${CMAKE_SOURCE_DIR}/po)

ADD_CUSTOM_TARGET (gettext-export
                   cd ${SRC_PO} && find ../dnf -iname "*.py" |
                   xargs xgettext --from-code=UTF-8 --keyword=P_:1,2 --output=${SRC_PO}/dnf.pot &&
                   zanata-cli -e -B push --project-config ${SRC_PO}/zanata.xml
                   COMMENT "Pushing translation source file to transifex")
ADD_CUSTOM_TARGET (gettext-update
                   zanata-cli -e -B pull --project-config ${SRC_PO}/zanata.xml
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
