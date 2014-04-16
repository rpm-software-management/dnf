#
#  bash completion support for dnf's console commands.
#  Based on zif's bash completion code
#
#  Copyright (C) 2008 - 2010 James Bowes <jbowes@repl.ca>
#  Copyright (C) 2010 Richard Hughes <richard@hughsie.com>
#  Copyright © 2013 Elad Alfassa <elad@fedoraproject.org>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
#  02110-1301  USA


__dnf_commandlist="
    clean
    check-update
    distro-sync
    downgrade
    remove
    erase
    group
    help
    history
    info
    install
    list
    makecache
    provides
    reinstall
    repolist
    search
    upgrade
    upgrade-to
    "

__dnfcomp ()
{
    local all c s=$'\n' IFS=' '$'\t'$'\n'
    local cur="${COMP_WORDS[COMP_CWORD]}"
    if [ $# -gt 2 ]; then
        cur="$3"
    fi
    for c in $1; do
        case "$c$4" in
        *.)    all="$all$c$4$s" ;;
        *)     all="$all$c$4 $s" ;;
        esac
    done
    IFS=$s
    COMPREPLY=($(compgen -P "$2" -W "$all" -- "$cur"))
    return
}

_dnf ()
{
    local i c=1 command
    local cur="${COMP_WORDS[COMP_CWORD]}"

    while [ $c -lt $COMP_CWORD ]; do
        i="${COMP_WORDS[c]}"
        case "$i" in
        --version|--help|--verbose|-h) ;;
        *) command="$i"; break ;;
        esac
        c=$((++c))
    done
    if [[ "$command" == "install" || "$command" == "update" || "$command" == "info" ]]; then
        if [ -r '/var/cache/dnf/available.cache' ]; then
            COMPREPLY=($(compgen -W "`egrep ^$cur /var/cache/dnf/available.cache`" -- "$cur"))
            return
        else
            COMPREPLY=($(compgen -W "`sudo dnf list --cacheonly 2>/dev/null | cut -d' ' -f1 | egrep ^$cur`" -- "$cur"))
            return
        fi
    fi
    if [[ "$command" == "remove" || "$command" == "erase" ]]; then
        if [ -r '/var/cache/dnf/installed.cache' ]; then
            COMPREPLY=($(compgen -W "`egrep ^$cur /var/cache/dnf/installed.cache`" -- "$cur"))
            return
        else
            COMPREPLY=($(compgen -W "`rpm -qav --qf '%{NAME}.%{ARCH}\n' | egrep ^$cur`" -- "$cur"))
            return
        fi
    fi

    if [ $c -eq $COMP_CWORD -a -z "$command" ]; then
        case "${COMP_WORDS[COMP_CWORD]}" in
        --*=*) COMPREPLY=() ;;
        --*)   __dnfcomp "
            --version
            --cacheonly
            --verbose
            --help
            --best
            --quiet
            --assumeno
            --assumeyes
            --refresh
            "
            ;;
        -*) __dnfcomp "
            -C
            -b
            -q
            -y
            "
            ;;
        *)     __dnfcomp "$__dnf_commandlist" ;;
        esac
        return
    fi

    case "$command" in
    *)           COMPREPLY=() ;;
    esac
}

complete -o default -o nospace -F _dnf dnf
