# dnf completion                                          -*- shell-script -*-
#
# This file is part of dnf.
#
# Copyright 2013 (C) Elad Alfassa <elad@fedoraproject.org>
# Copyright 2014 (C) Igor Gnatenko <i.gnatenko.brain@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA

_dnf_help_command()
{
    local cmd=$( dnf help $1 | grep -E "^$1" | tr "|" " " )
    cmd=${cmd#*[} && cmd=${cmd%%]*}
    eval "$2='$cmd'"
}

_dnf()
{
    local commandlist="$( compgen -W '$( dnf help | cut -d" " -s -f1 | sed -e "/^[A-Z]/d" -e "/:/d" )' )"

    local cur prev words cword
    _init_completion -s || return

    local commandix command
    for (( commandix=1; commandix < cword; commandix++ )); do
        if [[ ${words[commandix]} != -* ]]; then
            if [[ ${words[commandix-1]} != -* ]]; then
                command=${words[commandix]}
            fi
            break
        fi
    done

    # How many'th non-option arg (1-based) for $command are we completing?
    local i nth=1
    for (( i=commandix+1; i < cword; i++ )); do
        [[ ${words[i]} == -* ]] || (( nth++ ))
    done

    case $prev in
        -h|--help|--version)
            return
            ;;
        --enablerepo)
            COMPREPLY=( $( compgen -W '$( dnf --cacheonly repolist disabled | sed -e "1d" )' -- "$cur" ) )
            ;;
        --disablerepo )
            COMPREPLY=( $( compgen -W '$( dnf --cacheonly repolist enabled | sed -e "1d" | cut -d" " -f1 | tr -d "*" )' -- "$cur" ) )
            ;;
        *)
            ;;
    esac

    $split && return

    local comp
    local cache_file="/var/cache/dnf/packages.db"
    if [[ $command ]]; then

        case $command in
            install|update|info)
                if [ -r $cache_file ]; then
                    COMPREPLY=( $( compgen -W '$( sqlite3 $cache_file "select pkg from available WHERE pkg LIKE \"$cur%\"" )' ) )
                else
                    COMPREPLY=( $( compgen -W '$( dnf --cacheonly list $cur* 2>/dev/null | cut -d' ' -f1 )' -- "$cur" ) )
                fi
                [[ $command != "info" ]] && ext='@(rpm)' || ext=''
                ;;
            remove|erase)
                if [ -r $cache_file ]; then
                    COMPREPLY=( $( compgen -W '$( sqlite3 $cache_file "select pkg from installed WHERE pkg LIKE \"$cur%\"" )' ) )
                else
                    COMPREPLY=( $( compgen -W '$( rpm -qav --qf "%{NAME}.%{ARCH}\n" | grep -E "^$cur" )' -- "$cur" ) )
                fi
                ext=''
                ;;
            help)
                case $nth in
                    1)
                        COMPREPLY=( $( compgen -W '$( echo $commandlist )' -- "$cur" ) )
                        ;;
                    *)
                        ;;
                esac
                ext=''
                ;;
            clean)
                _dnf_help_command "clean" comp
                COMPREPLY=( $( compgen -W '$( echo $comp )' -- "$cur" ) )
                ext=''
                ;;
            repolist)
                case $nth in
                    1)
                        _dnf_help_command "repolist" comp
                        COMPREPLY=( $( compgen -W '$( echo $comp )' -- "$cur" ) )
                        ;;
                    *)
                        ;;
                esac
                ext=''
                ;;
            group)
                case $nth in
                    1)
                        _dnf_help_command "group" comp
                        COMPREPLY=( $( compgen -W '$( echo $comp )' -- "$cur" ) )
                        ;;
                    *)
                        ;;
                esac
                ext=''
                ;;
            *)
                ext=''
                ;;
        esac
        [[ ${#COMPREPLY[@]} -eq 0 ]] && [[ -n $ext ]] && _filedir $ext
        return

    fi

    if [[ $cur == -* ]]; then
        COMPREPLY=( $( compgen -W '$( _parse_help "$1" )' -- "$cur" ) )
        [[ $COMPREPLY == *= ]] && compopt -o nospace
    elif [[ ! $command ]]; then
        [[ $prev != -* ]] && COMPREPLY=( $( compgen -W '$( echo $commandlist )' -- "$cur" ) )
    fi
} &&
complete -F _dnf dnf
