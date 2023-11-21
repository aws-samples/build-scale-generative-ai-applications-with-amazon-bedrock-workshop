"""
bdrk_reinvent Streamlit stack
"""

import json
import os
from pathlib import Path

from aws_cdk import CfnOutput as output
from aws_cdk import NestedStack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_s3 as _s3
from aws_cdk.aws_ecr_assets import DockerImageAsset
from constructs import Construct
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk.aws_wafv2 import CfnWebACL
from aws_cdk.aws_cloudfront_origins import LoadBalancerV2Origin
import aws_cdk as cdk


class bdrk_reinventStreamlitStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        stack_name: str,
        ecs_cpu: int = 512,
        ecs_memory: int = 1024,
        client_id: str = None,
        api_uri: str = None,
        cover_image_url: str = None,
        cover_image_login_url: str = None,
        assistant_avatar: str = "assistant",
        open_to_public_internet=False,
        ip_address_allowed: list = None,
        retriever_options: list = None,
        sm_endpoints: dict = None,
        custom_header_name="X-Custom-Header",
        custom_header_value="MyNewCustomHeaderValue",
        **kwargs,
    ) -> None:
        super().__init__(scope, id, **kwargs)

        self.prefix = stack_name
        self.ecs_cpu = ecs_cpu
        self.ecs_memory = ecs_memory
        self.client_id = client_id
        self.api_uri = api_uri
        self.cover_image_url = cover_image_url
        self.cover_image_login_url = cover_image_login_url
        self.assistant_avatar = assistant_avatar
        self.ip_address_allowed = ip_address_allowed
        self.custom_header_name = custom_header_name
        self.custom_header_value = custom_header_value

        self.retriever_options = retriever_options if retriever_options is not None else ["N/A"]

        self.docker_asset = self.build_docker_push_ecr()
        self.vpc = self.create_webapp_vpc(open_to_public_internet=open_to_public_internet)

        self.cluster, self.alb, self.cloudfront = self.create_ecs_and_alb(
            open_to_public_internet=open_to_public_internet
        )

        # Add to hosted UI in Cognito Console:
        #   https://bdrk_reinvent.click
        #   https://bdrk_reinvent.click/oauth2/idpresponse

        self.alb_dns_name = output(self, id="AlbDnsName", value=self.alb.load_balancer_dns_name)
        self.cloudfront_distribution_name = output(
            self, id="cloudfront_distribution_name", value=self.cloudfront.domain_name
        )
        ## **************** Tags ****************
        Tags.of(self).add("StackName", id)
        Tags.of(self).add("Team", "Bedrock Workshop")

    def build_docker_push_ecr(self):
        # ECR: Docker build and push to ECR
        return DockerImageAsset(
            self,
            "StreamlitImg",
            # asset_name = f"{prefix}-streamlit-img",
            directory=os.path.join(Path(__file__).parent.parent.parent, "assets/streamlit"),
        )

    def create_webapp_vpc(self, open_to_public_internet=False):
        # VPC for ALB and ECS cluster
        vpc = ec2.Vpc(
            self,
            "WebappVpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            vpc_name=f"{self.prefix}-stl-vpc",
            nat_gateways=1,
        )

        self.ecs_security_group = ec2.SecurityGroup(
            self,
            "SecurityGroupECS",
            vpc=vpc,
            security_group_name=f"{self.prefix}-stl-ecs-sg",
        )
        self.ecs_security_group.add_ingress_rule(
            peer=self.ecs_security_group,
            connection=ec2.Port.all_traffic(),
            description="Within Security Group",
        )

        self.alb_security_group = ec2.SecurityGroup(
            self,
            "SecurityGroupALB",
            vpc=vpc,
            security_group_name=f"{self.prefix}-stl-alb-sg",
        )
        self.alb_security_group.add_ingress_rule(
            peer=self.alb_security_group,
            connection=ec2.Port.all_traffic(),
            description="Within Security Group",
        )

        if self.ip_address_allowed:
            for ip in self.ip_address_allowed:
                if ip.startswith("pl-"):
                    _peer = ec2.Peer.prefix_list(ip)
                    # cf https://apll.tools.aws.dev/#/
                else:
                    _peer = ec2.Peer.ipv4(ip)
                    # cf https://dogfish.amazon.com/#/search?q=Unfabric&attr.scope=PublicIP
                self.alb_security_group.add_ingress_rule(
                    peer=_peer,
                    connection=ec2.Port.tcp(80),
                )

        # Change IP address to developer IP for testing
        # self.alb_security_group.add_ingress_rule(peer=ec2.Peer.ipv4("1.2.3.4/32"),
        # connection=ec2.Port.tcp(443), description = "Developer IP")

        self.ecs_security_group.add_ingress_rule(
            peer=self.alb_security_group,
            connection=ec2.Port.tcp(8501),
            description="ALB traffic",
        )

        return vpc

    def create_ecs_and_alb(self, open_to_public_internet=False):
        # ECS cluster and service definition

        cluster = ecs.Cluster(self, "Cluster", enable_fargate_capacity_providers=True, vpc=self.vpc)

        alb_suffix = "" if open_to_public_internet else "-priv"

        # ALB to connect to ECS
        alb = elbv2.ApplicationLoadBalancer(
            self,
            f"{self.prefix}-alb{alb_suffix}",
            vpc=self.vpc,
            internet_facing=open_to_public_internet,
            load_balancer_name=f"{self.prefix}-stl{alb_suffix}",
            security_group=self.alb_security_group,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        fargate_task_definition = ecs.FargateTaskDefinition(
            self,
            "WebappTaskDef",
            memory_limit_mib=self.ecs_memory,
            cpu=self.ecs_cpu,
        )

        # app_uri = f"http://{alb.load_balancer_dns_name}"

        fargate_task_definition.add_container(
            "WebContainer",
            # Use an image from DockerHub
            image=ecs.ContainerImage.from_docker_image_asset(self.docker_asset),
            port_mappings=[ecs.PortMapping(container_port=8501, protocol=ecs.Protocol.TCP)],
            environment={  # "COGNITO_DOMAIN" : self.cognito_domain.domain_name,
                "CLIENT_ID": self.client_id,
                "API_URI": self.api_uri,
                "COVER_IMAGE_URL": self.cover_image_url,
                "COVER_IMAGE_LOGIN_URL": self.cover_image_login_url,
            },
            logging=ecs.LogDrivers.aws_logs(stream_prefix="WebContainerLogs"),
        )

        service = ecs.FargateService(
            self,
            "StreamlitECSService",
            cluster=cluster,
            task_definition=fargate_task_definition,
            service_name=f"{self.prefix}-stl-front",
            security_groups=[self.ecs_security_group],
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
        )

        """'
        Code for https traffic with certificate

        ecs_target_group = alb.ApplicationTargetGroup(
            self,
            "ecs-target-group",
            port=8501,
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
        )

        https_listener = alb.add_listener(
            "Listener",
            port=443,
            certificates=[certificate]
            ),
        )

        http_redirect = alb.add_redirect(
            source_port=80,
            source_protocol=elbv2.ApplicationProtocol.HTTP,
            target_port=443,
            target_protocol=elbv2.ApplicationProtocol.HTTPS,
        )
        """

        # ********* Cloudfront distribution *********

        # Add ALB as CloudFront Origin
        origin = LoadBalancerV2Origin(
            alb,
            custom_headers={self.custom_header_name: self.custom_header_value},
            origin_shield_enabled=False,
            protocol_policy=cloudfront.OriginProtocolPolicy.HTTP_ONLY,
        )

        cloudfront_distribution = cloudfront.Distribution(
            self,
            f"{self.prefix}-cf-dist",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER,
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
        )

        # ********* ALB Listener *********
        http_listener = alb.add_listener(
            f"{self.prefix}-http-listener{alb_suffix}",
            port=80,
            open=not (bool(self.ip_address_allowed)),
        )

        http_listener.add_targets(
            f"{self.prefix}-tg{alb_suffix}",
            target_group_name=f"{self.prefix}-tg{alb_suffix}",
            port=8501,
            priority=1,
            conditions=[elbv2.ListenerCondition.http_header(self.custom_header_name, [self.custom_header_value])],
            protocol=elbv2.ApplicationProtocol.HTTP,
            targets=[service],
        )
        # add a default action to the listener that will deny all requests that do not have the custom header
        http_listener.add_action(
            "default-action",
            action=elbv2.ListenerAction.fixed_response(
                status_code=403,
                content_type="text/plain",
                message_body="Access denied",
            ),
        )

        return cluster, alb, cloudfront_distribution
