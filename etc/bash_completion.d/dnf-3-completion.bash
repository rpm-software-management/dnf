# dnf-3 completion                                        -*- shell-script -*-
#
# This file is part of dnf-3.
#
# Copyright 2013 (C) Elad Alfassa <elad@fedoraproject.org>
# Copyright 2014-2015 (C) Igor Gnatenko <i.gnatenko.brain@gmail.com>
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

_dnf_3_help_command()
{
    local cmd=$( dnf-3 help $1 | grep -E "^$1" | tr "|" " " )
    cmd=${cmd#*[} && cmd=${cmd%%]*}
    eval "$2='$cmd'"
}

_dnf_3()
{
    local commandlist="$( compgen -W '$( LANG=C dnf-3 help | cut -d" " -s -f1 | LANG=C sed -e "/^[A-Z]/d" -e "/:/d" )' )"

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
            COMPREPLY=( $( compgen -W '$( dnf-3 --cacheonly repolist disabled | sed -e "1d" )' -- "$cur" ) )
            ;;
        --disablerepo )
            COMPREPLY=( $( compgen -W '$( dnf-3 --cacheonly repolist enabled | sed -e "1d" | cut -d" " -f1 | tr -d "*" )' -- "$cur" ) )
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
                if [[ "$cur" == \.* ]] || [[ "$cur" == \/* ]]; then
                    [[ $command != "info" ]] && ext='@(rpm)' || ext=''
                else
                    if [ -r $cache_file ]; then
                        COMPREPLY=( $( compgen -W '$( sqlite3 $cache_file "select pkg from available WHERE pkg LIKE \"$cur%\"" )' ) )
                    else
                        COMPREPLY=( $( compgen -W '$( python << END
import dnf
import os
import logging
class NullHandler(logging.Handler):
    def emit(self, record):
        pass
h = NullHandler()
logging.getLogger("dnf").addHandler(h)
b = dnf.Base()
b.read_all_repos()
if not dnf.util.am_i_root():
    cachedir = dnf.yum.misc.getCacheDir()
    b.conf.cachedir = cachedir
b.conf.substitutions["releasever"] = dnf.rpm.detect_releasever("/")
suffix = dnf.conf.parser.substitute(dnf.const.CACHEDIR_SUFFIX, b.conf.substitutions)
for repo in b.repos.values():
    repo.basecachedir = os.path.join(b.conf.cachedir, suffix)
    repo.md_only_cached = True
try:
    b.fill_sack()
except dnf.exceptions.RepoError:
    pass
q = b.sack.query().available()
for pkg in q:
    print("{}.{}").format(pkg.name, pkg.arch)
END
)' -- "$cur" ) )
                    fi
                fi
                ;;
            remove|erase|downgrade)
                if [[ "$cur" == \.* ]] || [[ "$cur" == \/* ]]; then
                    [[ $command != "info" ]] && ext='@(rpm)' || ext=''
                else
                    [ -r $cache_file ] && installed=$( sqlite3 $cache_file "select pkg from installed WHERE pkg LIKE \"$cur%\"" 2>/dev/null )
                     if [ $? -eq 0 ]; then
                        COMPREPLY=( $( compgen -W '$( echo $installed )' ) )
                    else
                        COMPREPLY=( $( compgen -W '$( python << END
import hawkey
sack = hawkey.Sack()
sack.load_system_repo()
q = hawkey.Query(sack).filter(reponame=hawkey.SYSTEM_REPO_NAME)
for pkg in q:
    print("{}.{}").format(pkg.name, pkg.arch)
END
)' -- "$cur" ) )
                    fi
                fi
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
                _dnf_3_help_command "clean" comp
                COMPREPLY=( $( compgen -W '$( echo $comp )' -- "$cur" ) )
                ext=''
                ;;
            repolist)
                case $nth in
                    1)
                        _dnf_3_help_command "repolist" comp
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
                        _dnf_3_help_command "group" comp
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
complete -F _dnf_3 dnf-3
