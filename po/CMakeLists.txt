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
