import os
import aws_cdk as cdk
from pathlib import Path

# from cdk_nag import AwsSolutionsChecks, NagSuppressions

from infra.bdrk_reinvent_stack import bdrkReinventStack

import yaml
from yaml.loader import SafeLoader


with open(os.path.join(Path(__file__).parent, "config.yml"), "r") as ymlfile:
    stack_config = yaml.load(ymlfile, Loader=SafeLoader)

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("CDK_DEFAULT_REGION"))

# cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# NagSuppressions.add_resource_suppressions(
#     app,
#     [
#         {
#             "id": "AwsSolutions-IAM5",
#             "reason": "IAM permissions have been scoped by least principle but still need wildcards.",
#         },
#     ],
# )


stack = bdrkReinventStack(scope=app, stack_name=stack_config["stack_name"], config=stack_config, env=env)
app.synth()
