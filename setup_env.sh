#run source setup_env to correctly set up python environment
SWEEPER_ROOT=`dirname "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"`
PYTHONPATH=${SWEEPER_ROOT}/python_vidi:${SWEEPER_ROOT}/src:${PYTHONPATH}
