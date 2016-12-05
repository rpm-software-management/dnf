# pushing/pulling translations to zanata

ADD_CUSTOM_TARGET (gettext-export
                   cd ${CMAKE_CURRENT_SOURCE_DIR} && find ../dnf -iname "*.py" |
                   xargs xgettext --from-code=UTF-8 --keyword=P_:1,2 --output=${CMAKE_CURRENT_SOURCE_DIR}/dnf.pot &&
                   zanata-cli -e -B push --project-config ${CMAKE_CURRENT_SOURCE_DIR}/zanata.xml
                   COMMENT "Pushing translation source file to transifex")
ADD_CUSTOM_TARGET (gettext-update
                   zanata-cli -e -B pull --project-config ${CMAKE_CURRENT_SOURCE_DIR}/zanata.xml
                   DEPENDS gettext-export
                   COMMENT "Updating translation files from transifex")

FIND_PACKAGE(Gettext)
IF (GETTEXT_FOUND)
    # this process unfortunately reformats .po files so copy them
    FILE(GLOB POS ${CMAKE_CURRENT_SOURCE_DIR}/*.po)
    FILE(COPY ${POS} DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
    FILE(GLOB POS_BIN ${CMAKE_CURRENT_BINARY_DIR/*.po)
    GETTEXT_CREATE_TRANSLATIONS(${CMAKE_CURRENT_SOURCE_DIR}/dnf.pot ALL ${POS_BIN})
ENDIF()
