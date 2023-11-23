
#!/bin/bash

# Specify the desired volume size in GiB as a command line argument. If not specified, default to 20 GiB.
SIZE=50


start_time_resize=$(date +%s)

# Get the ID of the environment host Amazon EC2 instance.
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 60")
INSTANCEID=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/instance-id 2> /dev/null)
REGION=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" -v http://169.254.169.254/latest/meta-data/placement/region 2> /dev/null)

# Get the ID of the Amazon EBS volume associated with the instance.
VOLUMEID=$(aws ec2 describe-instances \
  --instance-id $INSTANCEID \
  --query "Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId" \
  --output text \
  --region $REGION)

# Resize the EBS volume.
aws ec2 modify-volume --volume-id $VOLUMEID --size $SIZE

# Wait for the resize to finish.
while [ \
  "$(aws ec2 describe-volumes-modifications \
    --volume-id $VOLUMEID \
    --filters Name=modification-state,Values="optimizing","completed" \
    --query "length(VolumesModifications)"\
    --output text)" != "1" ]; do
sleep 1
done

# Check if we're on an NVMe filesystem
if [[ -e "/dev/xvda" && $(readlink -f /dev/xvda) = "/dev/xvda" ]]
then
# Rewrite the partition table so that the partition takes up all the space that it can.
  sudo growpart /dev/xvda 1
# Expand the size of the file system.
# Check if we're on AL2
  STR=$(cat /etc/os-release)
  SUB="VERSION_ID=\"2\""
  if [[ "$STR" == *"$SUB"* ]]
  then
    sudo xfs_growfs -d /
  else
    sudo resize2fs /dev/xvda1
  fi

else
# Rewrite the partition table so that the partition takes up all the space that it can.
  sudo growpart /dev/nvme0n1 1

# Expand the size of the file system.
# Check if we're on AL2
  STR=$(cat /etc/os-release)
  SUB="VERSION_ID=\"2\""
  if [[ "$STR" == *"$SUB"* ]]
  then
    sudo xfs_growfs -d /
  else
    sudo resize2fs /dev/nvme0n1p1
  fi
fi

# End time and duration
end_time_resize=$(date +%s)
duration_resize=$((end_time_resize - start_time_resize))
echo "Time taken to build everything: $duration_resize seconds"

# sleep for 60 seconds
sleep 60 

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