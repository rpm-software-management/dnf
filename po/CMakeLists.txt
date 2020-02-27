# pulling translations from weblate

set(WEBLATE_REPO_URL "git@github.com:rpm-software-management/${PROJECT_NAME}-l10n.git")
set(WEBLATE_REPO_BRANCH "master")
set(WEBLATE_REPO_PATH ${CMAKE_CURRENT_BINARY_DIR}/tmp-weblate-repo)

find_package(Git)
find_package(Gettext)

if (GIT_FOUND)
    # output _weblate-clone is never created so the clonning of weblate repo is always processed
    # and fresh *.po files are used
    add_custom_command(OUTPUT _weblate-clone
        COMMENT "Clonning weblate repo"
        COMMAND ${CMAKE_COMMAND} -E remove_directory ${WEBLATE_REPO_PATH}
        COMMAND ${GIT_EXECUTABLE} clone --depth=1 -b ${WEBLATE_REPO_BRANCH} ${WEBLATE_REPO_URL} ${WEBLATE_REPO_PATH}
        BYPRODUCTS ${WEBLATE_REPO_PATH}
    )

    add_custom_target(gettext-update
        COMMENT "Updating translation files from weblate repo"

        COMMAND ${CMAKE_COMMAND} -E copy ${WEBLATE_REPO_PATH}/*.po .
        COMMAND ${CMAKE_COMMAND} -E copy ${WEBLATE_REPO_PATH}/${PROJECT_NAME}.pot .
        COMMAND ${CMAKE_SOURCE_DIR}/scripts/sanitize_po_files.py *.po

        DEPENDS _weblate-clone

        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        )
endif()


IF (GETTEXT_FOUND)
    # this process unfortunately reformats .po files so copy them
    FILE(GLOB POS ${CMAKE_CURRENT_SOURCE_DIR}/*.po)
    FILE(COPY ${POS} DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
    FILE(GLOB POS_BIN ${CMAKE_CURRENT_BINARY_DIR}/*.po)
    GETTEXT_CREATE_TRANSLATIONS(${CMAKE_CURRENT_SOURCE_DIR}/${PROJECT_NAME}.pot ALL ${POS_BIN})
ENDIF()
