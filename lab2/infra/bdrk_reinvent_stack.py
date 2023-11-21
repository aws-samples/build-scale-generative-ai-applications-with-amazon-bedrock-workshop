"""
bdrk_reinvent stack
"""

from typing import Any, Dict

from aws_cdk import Aws
from aws_cdk import CfnOutput as output
from aws_cdk import RemovalPolicy, Stack, Tags

from constructs import Construct

from infra.constructs.bdrk_reinvent_api import bdrk_reinventAPIConstructs
from infra.constructs.bdrk_reinvent_layers import bdrk_reinventLambdaLayers
from infra.stacks.bdrk_reinvent_streamlit import bdrk_reinventStreamlitStack

sm_endpoints = {}


class bdrkReinventStack(Stack):
    """
    bdrk_reinvent stack
    """

    def __init__(self, scope: Construct, stack_name: str, config: Dict[str, Any], **kwargs) -> None:  # noqa: C901
        super().__init__(scope, stack_name, **kwargs)

        ## **************** Lambda layers ****************

        self.layers = bdrk_reinventLambdaLayers(self, f"{stack_name}-layers", stack_name=stack_name)

        ## ********** Bedrock configs ***********
        bedrock_region = kwargs["env"].region
        bedrock_role_arn = None

        if "bedrock" in config:
            if "region" in config["bedrock"]:
                bedrock_region = (
                    kwargs["env"].region if config["bedrock"]["region"] == "None" else config["bedrock"]["region"]
                )

        ## ********** Authentication configs ***********
        mfa_enabled = True
        if "authentication" in config:
            if "MFA" in config["authentication"]:
                mfa_enabled = config["authentication"]["MFA"]

        ## **************** API Constructs  ****************
        self.api_constructs = bdrk_reinventAPIConstructs(
            self,
            f"{stack_name}-API",
            stack_name=stack_name,
            layers=self.layers,
            bedrock_region=bedrock_region,
            bedrock_role_arn=bedrock_role_arn,
            mfa_enabled=mfa_enabled,
        )

        ## **************** Streamlit NestedStack ****************
        if config["streamlit"]["deploy_streamlit"]:
            self.streamlit_constructs = bdrk_reinventStreamlitStack(
                self,
                f"{stack_name}-STREAMLIT",
                stack_name=stack_name,
                client_id=self.api_constructs.client_id,
                api_uri=self.api_constructs.api_uri,
                ecs_cpu=config["streamlit"]["ecs_cpu"],
                ecs_memory=config["streamlit"]["ecs_memory"],
                cover_image_url=config["streamlit"]["cover_image_url"],
                cover_image_login_url=config["streamlit"]["cover_image_login_url"],
                assistant_avatar=config["streamlit"]["assistant_avatar"],
                open_to_public_internet=config["streamlit"]["open_to_public_internet"],
                ip_address_allowed=config["streamlit"].get("ip_address_allowed"),
                custom_header_name=config["cloudfront"]["custom_header_name"],
                custom_header_value=config["cloudfront"]["custom_header_value"],
            )

            self.alb_dns_name = output(
                self,
                id="AlbDnsName",
                value=self.streamlit_constructs.alb.load_balancer_dns_name,
            )

            self.cloudfront_distribution_name = output(
                self,
                id="cloudfront_distribution_domain_name",
                value=self.streamlit_constructs.cloudfront.domain_name,
            )

        ## **************** Tags ****************
        Tags.of(self).add("StackName", stack_name)
        Tags.of(self).add("Team", "Bedrock Workshop")
