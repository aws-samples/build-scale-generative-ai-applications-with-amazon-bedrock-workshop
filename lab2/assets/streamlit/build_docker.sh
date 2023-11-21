# Configure Account and region

AWS_ACCOUNT_ID=$1
AWS_REGION='eu-west-1'

IMAGE_TAG='demo-streamlit'
ECR_REPOSITORY='demo-streamlit'

docker build . --tag $IMAGE_TAG
docker tag $IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest
eval $(aws ecr get-login --no-include-email)
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:latest