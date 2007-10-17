import sys

# Adjust path so we can see the src modules running from branch as well
# as test dir:
sys.path.insert(0, '../../')
sys.path.insert(0, '../')
sys.path.insert(0, './')

new_behavior = "--new_behavior" in sys.argv
sys.argv = filter("--new_behavior".__ne__, sys.argv)
