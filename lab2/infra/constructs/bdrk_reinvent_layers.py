"""
bdrk_reinvent API constructs
"""

from aws_cdk import aws_lambda as _lambda
from constructs import Construct


class bdrk_reinventLambdaLayers(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stack_name,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bedrock_compatible_sdk = _lambda.LayerVersion(
            self,
            f"{stack_name}-bedrock-compatible-sdk-layer",
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            code=_lambda.Code.from_asset("./assets/layers/bedrock-compatible-sdk.zip"),
            description="A layer for bedrock compatible boto3 sdk",
            layer_version_name=f"{stack_name}-bedrock-compatible-sdk-layer-3",
        )

        # self.jwt = _lambda.LayerVersion(
        #     self,
        #     f"{stack_name}-jwt",
        #     compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
        #     code=_lambda.Code.from_asset("./assets/layers/jwt.zip"),
        #     description="A layer with jwt to decode tokens",
        #     layer_version_name=f"{stack_name}-jwt",
        # )
