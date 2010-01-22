# bash completion for yum

# arguments:
#   1 = argument to "yum list" (all, available, updates etc)
#   2 = current word to be completed
_yum_list()
{
    if [ "$1" = all ] ; then
        # Try to strip in between headings like "Available Packages" - would
        # be nice if e.g. -d 0 did that for us.  This will obviously only work
        # for English :P
        COMPREPLY=( "${COMPREPLY[@]}"
            $( ${yum:-yum} -d 0 -C list $1 "$2*" 2>/dev/null | \
                sed -ne '/^Available /d' -e '/^Installed /d' -e '/^Updated /d' \
                -e 's/[[:space:]].*//p' ) )
    else
        # Drop first line (e.g. "Updated Packages") - would be nice if e.g.
        # -d 0 did that for us.
        COMPREPLY=( "${COMPREPLY[@]}"
            $( ${yum:-yum} -d 0 -C list $1 "$2*" 2>/dev/null | \
                sed -ne 1d -e 's/[[:space:]].*//p' ) )
    fi
}

# arguments:
#   1 = argument to "yum repolist" (enabled, disabled etc)
#   2 = current word to be completed
_yum_repolist()
{
    # TODO: add -d 0 when http://yum.baseurl.org/ticket/29 is fixed
    #       (for now --noplugins is used to get rid of "Loaded plugins: ...")
    # Drop first ("repo id      repo name") and last ("repolist: ...") rows -
    # would be nice if e.g. -d 0 did that for us.
    COMPREPLY=( "${COMPREPLY[@]}"
        $( compgen -W "$( ${yum:-yum} --noplugins -C repolist $1 2>/dev/null | \
            sed -ne '/^repo\s\{1,\}id/d' -e '/^repolist:/d' \
            -e 's/[[:space:]].*//p' )" -- "$2" ) )
}

# arguments:
#   1 = argument to "yum grouplist" (usually empty (""), or hidden)
#   2 = current word to be completed
_yum_grouplist()
{
    local IFS=$'\n'
    # TODO: add -d 0 when http://yum.baseurl.org/ticket/29 is fixed
    COMPREPLY=( $( compgen -W "$( ${yum:-yum} -C grouplist $1 "$2*" \
        2>/dev/null | sed -ne 's/^[[:space:]]\{1,\}\(.\{1,\}\)/\1/p' )" \
        -- "$2" ) )
}

# arguments:
#   1 = 1 or 0 to list enabled or disabled plugins
#   2 = current word to be completed
_yum_plugins()
{
    local val
    [ $1 = 1 ] && val='\(1\|yes\|true\|on\)' || val='\(0\|no\|false\|off\)'
    COMPREPLY=( "${COMPREPLY[@]}"
        $( compgen -W '$( command grep -il "^\s*enabled\s*=\s*$val" \
            /etc/yum/pluginconf.d/*.conf 2>/dev/null \
            | sed -ne "s|^.*/\([^/]\{1,\}\)\.conf$|\1|p" )' -- "$2" ) )
}

# arguments:
#   1 = current word to be completed
_yum_binrpmfiles()
{
    COMPREPLY=( "${COMPREPLY[@]}"
        $( compgen -f -o plusdirs -X '!*.rpm' -- "$1" ) )
    COMPREPLY=( $( compgen -W '"${COMPREPLY[@]}"' -X '*.src.rpm' ) )
    COMPREPLY=( $( compgen -W '"${COMPREPLY[@]}"' -X '*.nosrc.rpm' ) )
}

_yum()
{
    COMPREPLY=()
    local yum=$1
    local cur
    type _get_cword &>/dev/null && cur=`_get_cword` || cur=$2
    local prev=$3
    local cmds=( check check-update clean deplist downgrade groupinfo
        groupinstall grouplist groupremove help history info install list
        localinstall makecache provides reinstall remove repolist resolvedep
        search shell update upgrade version )

    local i c cmd
    for (( i=0; i < ${#COMP_WORDS[@]}-1; i++ )) ; do
        for c in ${cmds[@]} check-rpmdb erase groupupdate grouperase \
            whatprovides ; do
            [ ${COMP_WORDS[i]} = $c ] && cmd=$c && break
        done
        [ -z $cmd ] || break
    done

    case $cmd in

        check|check-rpmdb)
            COMPREPLY=( $( compgen -W 'dependencies duplicates all' \
                -- "$cur" ) )
            return 0
            ;;

        check-update|grouplist|makecache|provides|whatprovides|resolvedep|\
        search|version)
            return 0
            ;;

        clean)
            if [ "$prev" = clean ] ; then
                COMPREPLY=( $( compgen -W 'expire-cache packages headers
                    metadata cache dbcache all' -- "$cur" ) )
            fi
            return 0
            ;;

        deplist)
            if [[ "$cur" == */* ]] ; then
                _yum_binrpmfiles "$cur"
            else
                _yum_list all "$cur"
            fi
            return 0
            ;;

        downgrade|reinstall)
            if [[ "$cur" == */* ]] ; then
                _yum_binrpmfiles "$cur"
            else
                _yum_list installed "$cur"
            fi
            return 0
            ;;

        erase|remove)
            _yum_list installed "$cur"
            return 0
            ;;

        group*)
            _yum_grouplist "" "$cur"
            return 0
            ;;

        help)
            if [ "$prev" = help ] ; then
                COMPREPLY=( $( compgen -W '${cmds[@]}' -- "$cur" ) )
            fi
            return 0
            ;;

        history)
            case $prev in
                history)
                    COMPREPLY=( $( compgen -W 'info list summary undo redo
                        new' -- "$cur" ) )
                    ;;
                undo|redo)
                    COMPREPLY=( $( compgen -W "last $( $yum -d 0 -C history \
                        2>/dev/null | \
                        sed -ne 's/^[[:space:]]*\([0-9]\{1,\}\).*/\1/p' )" \
                        -- "$cur" ) )
                    ;;
            esac
            return 0
            ;;

        info)
            _yum_list all "$cur"
            return 0
            ;;

        install)
            if [[ "$cur" == */* ]] ; then
                _yum_binrpmfiles "$cur"
            else
                _yum_list available "$cur"
            fi
            return 0
            ;;

        list)
            if [ "$prev" = list ] ; then
                COMPREPLY=( $( compgen -W 'all available updates installed
                    extras obsoletes recent' -- "$cur" ) )
            fi
            return 0
            ;;

        localinstall|localupdate)
            _yum_binrpmfiles "$cur"
            return 0
            ;;

        repolist)
            if [ "$prev" = repolist ] ; then
                COMPREPLY=( $( compgen -W 'all enabled disabled' -- "$cur" ) )
            fi
            return 0
            ;;

        shell)
            if [ "$prev" = shell ] ; then
                COMPREPLY=( $( compgen -f -o plusdirs -- "$cur" ) )
            fi
            return 0
            ;;

        update|upgrade)
            if [[ "$cur" == */* ]] ; then
                _yum_binrpmfiles "$cur"
            else
                _yum_list updates "$cur"
            fi
            return 0
            ;;
    esac

    local split=false
    type _split_longopt &>/dev/null && _split_longopt && split=true

    case $prev in

        -d|--debuglevel|-e|--errorlevel)
            COMPREPLY=( $( compgen -W '0 1 2 3 4 5 6 7 8 9 10' -- "$cur" ) )
            return 0
            ;;

        --rpmverbosity)
            COMPREPLY=( $( compgen -W 'info critical emergency error warn
                debug' -- "$cur" ) )
            return 0
            ;;

        -c|--config)
            COMPREPLY=( $( compgen -f -o plusdirs -X "!*.conf" -- "$cur" ) )
            return 0
            ;;

        --installroot|--downloaddir)
            COMPREPLY=( $( compgen -d -- "$cur" ) )
            return 0
            ;;

        --enablerepo)
            _yum_repolist disabled "$cur"
            return 0
            ;;

        --disablerepo)
            _yum_repolist enabled "$cur"
            return 0
            ;;

        --disableexcludes)
            _yum_repolist all "$cur"
            COMPREPLY=( $( compgen -W '${COMPREPLY[@]} all main' -- "$cur" ) )
            return 0
            ;;

        --enableplugin)
            _yum_plugins 0 "$cur"
            return 0
            ;;

        --disableplugin)
            _yum_plugins 1 "$cur"
            return 0
            ;;

        --color)
            COMPREPLY=( $( compgen -W 'always auto never' -- "$cur" ) )
            return 0
            ;;

        -R|--randomwait|-x|--exclude|-h|--help|--version|--releasever|--cve|\
        --bz|--advisory|--tmprepo|--verify-filenames)
            return 0
            ;;

        --download-order)
            COMPREPLY=( $( compgen -W 'default smallestfirst largestfirst' \
                -- "$cur" ) )
            return 0
            ;;

        --override-protection)
            _yum_list installed "$cur"
            return 0
            ;;

        --verify-configuration-files)
            COMPREPLY=( $( compgen -W '1 0' -- "$cur" ) )
            return 0
            ;;
    esac

    $split && return 0

    COMPREPLY=( $( compgen -W '--help --tolerant --cacheonly --config
        --randomwait --debuglevel --showduplicates --errorlevel --rpmverbosity
        --quiet --verbose --assumeyes --version --installroot --enablerepo
        --disablerepo --exclude --disableexcludes --obsoletes --noplugins
        --nogpgcheck --disableplugin --enableplugin --skip-broken --color
        --releasever ${cmds[@]}' -- "$cur" ) )
} &&
complete -F _yum -o filenames yum yummain.py

# Local variables:
# mode: shell-script
# sh-basic-offset: 4
# sh-indent-comment: t
# indent-tabs-mode: nil
# End:
# ex: ts=4 sw=4 et filetype=sh
