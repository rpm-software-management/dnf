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


__dnf_commandlist="$(compgen -W "`dnf help | sed -e "s/\(  \)\+.*$//g" -e "/^$/d" -e "/^[A-Z ]/d" -e "/:/d"`")"
# s/\(  \)\+.*$//g : remove description for commands
# /^$/d            : remove blank lines
# /^[A-Z ]/d       : remove lines starts with capital letter or with space (all commands in help starts without spaces)
# /:/d             : remove lines which contains ':' (now we have only commands, so commands can't contain this sym)

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
            COMPREPLY=($(compgen -W "`grep -E ^$cur /var/cache/dnf/available.cache`" -- "$cur"))
            return
        else
            COMPREPLY=($(compgen -W "`dnf list --cacheonly 2>/dev/null | cut -d' ' -f1 | grep -E ^$cur`" -- "$cur"))
            return
        fi
    fi
    if [[ "$command" == "remove" || "$command" == "erase" ]]; then
        if [ -r '/var/cache/dnf/installed.cache' ]; then
            COMPREPLY=($(compgen -W "`grep -E ^$cur /var/cache/dnf/installed.cache`" -- "$cur"))
            return
        else
            COMPREPLY=($(compgen -W "`rpm -qav --qf '%{NAME}.%{ARCH}\n' | grep -E ^$cur`" -- "$cur"))
            return
        fi
    fi
    if [[ "$command" == "help" ]]; then
      COMPREPLY=($(compgen -W "`echo $__dnf_commandlist`" -- "$cur"))
        return
    fi

    if [ $c -eq $COMP_CWORD -a -z "$command" ]; then
        case "${COMP_WORDS[COMP_CWORD]}" in
        --*=*) COMPREPLY=() ;;
        --*)   __dnfcomp "
            --allowerasing
            --best
            --cacheonly
            --config
            --randomwait
            --debuglevel
            --debugsolver
            --showduplicates
            --errorlevel
            --rpmverbosity
            --quiet
            --verbose
            --assumeyes
            --assumeno
            --version
            --installroot
            --enablerepo
            --disablerepo
            --exclude
            --disableexcludes
            --obsoletes
            --noplugins
            --nogpgcheck
            --disableplugin
            --color
            --releasever
            --setopt
            --refresh
            --help
            "
            ;;
        -*) __dnfcomp "
            -b
            -C
            -c
            -R
            -d
            -e
            -q
            -v
            -y
            -x
            -4
            -6
            -h
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
