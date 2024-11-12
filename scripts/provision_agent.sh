#!/bin/bash
# This script sets up the agent environment
echo "Setting up the agent environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "Agent environment setup complete."
