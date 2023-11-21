# Lab 2

## Prerequisites
You  need to add model access to Anthropic Claude (V2) and Amazon Titan (if possible). See the documentation for more: https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html#add-model-access

## Installation

1. Locate the `run.sh` file under Lab2 directory and make it executable:
`chmod +x run.sh`

2. Execute `run.sh`
`./run.sh`

The deployment of the application will take approximately 10 minutes. Once done it will show outputs like:

````
bdrkReinventStack.AlbDnsName = internal-bdrkReinventStack-stl-priv-********.us-east-1.elb.amazonaws.com
bdrkReinventStack.BucketName = bdrkreinventstack-data-046676399357
bdrkReinventStack.bdrkReinventStackAPIAPIEndpoint4FB601DD = https://ox3d8uym1g.execute-api.us-east-1.amazonaws.com
bdrkReinventStack.bdrkReinventStackAPICognitoClientID84CF997C = 2glsolf5tsd1j********
bdrkReinventStack.bdrkReinventStackAPIWSAPIEndpoint38A1018F = wss://kode5g2jke.execute-api.us-east-1.amazonaws.com/Prod
bdrkReinventStack.cloudfrontdistributiondomainname = d36kltsvayb4ge.cloudfront.net
Stack ARN:
arn:aws:cloudformation:us-east-1:046676*****:stack/bdrkReinventStack/cad08e40-773d-11ee-a2e9-0e52*****

✨  Total time: 467.83s
```

You can access the workshop using the CloudFront URL output of the CDK stack: `bdrkReinventStack.cloudfrontdistributiondomainname`


