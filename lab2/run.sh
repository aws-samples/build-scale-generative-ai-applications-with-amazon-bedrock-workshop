#!/bin/bash

# Exit if any command fails
set -e

start_time=$(date +%s)

# Check if Miniconda is installed and install it if not
if ! command -v conda &> /dev/null; then
    echo "Miniconda is not installed. Installing Miniconda..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
    bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda
    echo "Miniconda installed successfully."
fi

# Initialize Miniconda environment
export PATH="$HOME/miniconda/bin:$PATH"

# Initialize Conda in your shell (modify this line for different shells)
source $HOME/miniconda/etc/profile.d/conda.sh


echo "Initialized Conda in the shell. Currently in directory: $PWD"

# Start time
start_time_layers=$(date +%s)

# Create and activate a separate Conda environment for Lambda Layer
conda create -n lambda_layer_env python=3.9 -y
conda activate lambda_layer_env

# Install necessary packages in this environment
pip install boto3 

# Prepare directory for Lambda Layer
LAYER_DIR="./assets/layers/"
mkdir -p $LAYER_DIR/python

# Package the environment into a zip file
cp -r $HOME/miniconda/envs/lambda_layer_env/lib/python3.9/site-packages/* $LAYER_DIR/python/
cd $LAYER_DIR
zip -qr bedrock-compatible-sdk.zip python
if [ $? -eq 0 ]; then
    echo "Zip file created successfully."
    rm -rf python
    echo "Python directory removed."
else
    echo "There was an error creating the zip file."
fi

echo "Zipped the layer. Current directory is $PWD"

# Move the zip file to the right location
# mv bedrock-compatible-sdk.zip ../

# Cleanup (optional)
conda deactivate
conda env remove -n lambda_layer_env


# End time and duration
end_time_layers=$(date +%s)
duration_layers=$((end_time_layers - start_time_layers))
echo "Time taken to build layer: $duration_layers seconds"

echo "Current directory is $PWD"
echo "Moving back to root dir of lab2"

cd ../../

# Create and activate a Conda environment using Python 3.9
conda create -n bdrkenv python=3.9 -y
conda activate bdrkenv

pip install poetry==1.7.0

poetry install 

# sudo npm install -g aws-cdk@latest --force

# cd ./assets/streamlit

# poetry install

# cd ../../

cdk bootstrap 

cdk deploy --require-approval=never

# End time and duration
end_time=$(date +%s)
duration=$((end_time - start_time))
echo "Time taken to build everything: $duration seconds"