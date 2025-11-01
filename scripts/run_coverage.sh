#!/bin/bash

# Exit on error
set -e

# Default values
GENERATE_HTML=false
GENERATE_XML=false
FAIL_UNDER=80
OPEN_BROWSER=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --html)
            GENERATE_HTML=true
            shift
            ;;
        --xml)
            GENERATE_XML=true
            shift
            ;;
        --fail-under=*)
            FAIL_UNDER="${1#*=}"
            shift
            ;;
        --open-browser)
            OPEN_BROWSER=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create coverage directory if it doesn't exist
mkdir -p htmlcov

# Build the pytest command with coverage options
PYTEST_CMD="pytest --cov=app/api --cov-report=term-missing --cov-fail-under=${FAIL_UNDER}"

# Add HTML report if requested
if [ "$GENERATE_HTML" = true ]; then
    PYTEST_CMD+=" --cov-report=html"
fi

# Add XML report if requested
if [ "$GITHUB_ACTIONS" = "true" ] || [ "$GENERATE_XML" = true ]; then
    PYTEST_CMD+=" --cov-report=xml"
fi

# Run the tests with coverage
echo "Running tests with coverage..."
eval $PYTEST_CMD

# Generate coverage badge if coverage is installed
if command -v coverage-badge &> /dev/null; then
    echo "Generating coverage badge..."
    coverage-badge -o coverage.svg
    echo "Coverage badge generated: coverage.svg"
fi

# Open the HTML report in the default browser if requested
if [ "$OPEN_BROWSER" = true ] && [ "$GENERATE_HTML" = true ]; then
    echo "Opening coverage report in browser..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open "htmlcov/index.html"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        xdg-open "htmlcov/index.html"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        start "htmlcov\index.html"
    else
        echo "Could not detect OS to open browser. Please open htmlcov/index.html manually."
    fi
fi

echo "Coverage report generated at htmlcov/index.html"

# Keep the window open on Windows
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo "Press any key to continue..."
    read -n 1 -s
fi
