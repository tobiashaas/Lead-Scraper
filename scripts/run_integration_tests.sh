#!/bin/bash

# Exit on error
set -e

# Default values
VERBOSE=false
PARALLEL=false
COVERAGE=false
KEEP_DB=false
MARKERS=""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --parallel|-p)
            PARALLEL=true
            shift
            ;;
        --coverage|c)
            COVERAGE=true
            shift
            ;;
        --keep-db|k)
            KEEP_DB=true
            shift
            ;;
        --markers|-m)
            MARKERS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Set environment variables
export ENVIRONMENT=test
export DATABASE_URL=sqlite:///./test.db

# Create test database if it doesn't exist
if [ ! -f "test.db" ]; then
    echo -e "${GREEN}Creating test database...${NC}"
    alembic upgrade head
fi

# Build the pytest command
PYTEST_CMD="pytest tests/integration/ -m integration"

# Add verbosity if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD+=" -v"
fi

# Add parallel execution if requested
if [ "$PARALLEL" = true ]; then
    PYTEST_CMD+=" -n auto"
fi

# Add coverage if requested
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD+=" --cov=app/api --cov-report=term"
fi

# Add markers if specified
if [ -n "$MARKERS" ]; then
    PYTEST_CMD+=" -m \"$MARKERS\""
fi

# Add HTML report
PYTEST_CMD+=" --html=test-report.html --self-contained-html"

# Run the tests
echo -e "${GREEN}Running integration tests...${NC}"
echo -e "Command: $PYTEST_CMD"
eval $PYTEST_CMD

# Clean up test database if not keeping it
if [ "$KEEP_DB" = false ]; then
    echo -e "${GREEN}Cleaning up test database...${NC}"
    rm -f test.db
fi

echo -e "${GREEN}Test report generated at test-report.html${NC}"
