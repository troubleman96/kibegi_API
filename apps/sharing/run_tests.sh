#!/bin/bash
# Quick test runner for sharing system
# Usage: bash apps/sharing/run_tests.sh

echo "=========================================="
echo "KIBEGI FILE SHARING - TEST RUNNER"
echo "=========================================="
echo ""

cd /home/troubleman/projects/Kibegi/Backend

# Activate virtual environment
source venv/bin/activate

echo "Running all sharing tests..."
echo ""

# Run tests with verbose output
python manage.py test apps.sharing.tests -v 2 --keepdb

echo ""
echo "=========================================="
echo "TEST RUN COMPLETE"
echo "=========================================="
