"""
bdrk_reinvent API constructs
"""

import aws_cdk.aws_apigatewayv2_alpha as _apigw
import aws_cdk.aws_apigatewayv2_integrations_alpha as _integrations
from aws_cdk import Aws, CfnOutput, Duration, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as ddb
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sns as sns
from aws_cdk.aws_apigatewayv2_authorizers_alpha import HttpUserPoolAuthorizer
from constructs import Construct

QUERY_BEDROCK_TIMEOUT = 900


class bdrk_reinventAPIConstructs(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stack_name,
        # s3_data_bucket: _s3.Bucket,
        layers: Construct,
        bedrock_region: str,
        bedrock_role_arn: str = "",
        mfa_enabled: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # self.s3_data_bucket = s3_data_bucket

        self.bedrock_region = bedrock_region
        self.bedrock_role_arn = bedrock_role_arn

        self.stack_name = stack_name
        self.layers = layers

        self.prefix = stack_name[:16]
        self.create_cognito_user_pool(mfa_enabled)

        # **************** Create resources ****************
        self.create_dynamodb()
        self.create_sns_topic()
        self.create_roles()
        self.create_lambda_functions()

        self.authorizer = HttpUserPoolAuthorizer(
            "BooksAuthorizer", self.user_pool, user_pool_clients=[self.user_pool_client]
        )

        self.create_http_api()

        # Outputs
        CfnOutput(
            self,
            "API Endpoint",
            description="API Endpoint",
            value=self.api_uri,
        )
        CfnOutput(self, "Cognito Client ID",
                  description="Cognito Client ID", value=self.client_id)

    def create_http_api(self):
        log_group = logs.LogGroup(
            self,
            "ApiAccessLogs",
            log_group_name=f"{self.stack_name}-api-access-logs",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        # Create the HTTP API with CORS
        http_api = _apigw.HttpApi(
            self,
            f"{self.stack_name}-http-api",
            default_authorizer=self.authorizer,
            cors_preflight=_apigw.CorsPreflightOptions(
                allow_methods=[_apigw.CorsHttpMethod.POST],
                allow_origins=["*"],
                max_age=Duration.days(10),
            ),
        )

        # add content/bedrock to POST /
        http_api.add_routes(
            path="/content/bedrock",
            methods=[_apigw.HttpMethod.POST],
            integration=_integrations.HttpLambdaIntegration(
                "LambdaProxyIntegration", handler=self.bedrock_content_generation_lambda  # type: ignore
            ),
        )

        # add dynamo/put to POST /
        http_api.add_routes(
            path="/dynamo/put",
            methods=[_apigw.HttpMethod.POST],
            integration=_integrations.HttpLambdaIntegration(
                "LambdaProxyIntegration", handler=self.prompt_management_lambda),  # type: ignore
        )

        # add dynamo/put to POST /
        http_api.add_routes(
            path="/dynamo/get",
            methods=[_apigw.HttpMethod.GET],
            integration=_integrations.HttpLambdaIntegration(
                "LambdaProxyIntegration", handler=self.prompt_management_lambda),  # type: ignore
        )

        # add dynamo/put to POST /
        http_api.add_routes(
            path="/dynamo/delete",
            methods=[_apigw.HttpMethod.DELETE],
            integration=_integrations.HttpLambdaIntegration(
                "LambdaProxyIntegration", handler=self.prompt_management_lambda),  # type: ignore
        )

        # add sns/put to POST /
        http_api.add_routes(
            path="/sns/put",
            methods=[_apigw.HttpMethod.POST],
            integration=_integrations.HttpLambdaIntegration(
                "LambdaProxyIntegration", handler=self.sns_topic_lambda),  # type: ignore
        )

        self.api_uri = http_api.api_endpoint

    def create_cognito_user_pool(self, mfa_enabled):
        # Cognito User Pool

        # Define the password policy
        password_policy = cognito.PasswordPolicy(
            min_length=8,  # Minimum length of 8 characters
            require_lowercase=True,  # Require lowercase characters
            require_uppercase=True,  # Require uppercase characters
            require_digits=True,  # Require numeric characters
            require_symbols=True,  # Require special characters
        )

        if mfa_enabled:
            self.user_pool = cognito.UserPool(
                self,
                f"{self.prefix}-user-pool",
                user_pool_name=f"{self.prefix}-user-pool",
                auto_verify=cognito.AutoVerifiedAttrs(email=True),
                mfa=cognito.Mfa.REQUIRED,
                mfa_second_factor=cognito.MfaSecondFactor(sms=False, otp=True),
                self_sign_up_enabled=True,
                password_policy=password_policy,
                advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            )
        else:
            self.user_pool = cognito.UserPool(
                self,
                f"{self.prefix}-user-pool",
                user_pool_name=f"{self.prefix}-user-pool",
                auto_verify=cognito.AutoVerifiedAttrs(email=True),
                self_sign_up_enabled=True,
                password_policy=password_policy,
                advanced_security_mode=cognito.AdvancedSecurityMode.ENFORCED,
            )
        self.user_pool_client = self.user_pool.add_client(
            "customer-app-client",
            user_pool_client_name=f"{self.prefix}-client",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_password=True),
        )

        self.client_id = self.user_pool_client.user_pool_client_id

    # **************** DynamoDB ****************
    def create_dynamodb(self):
        self.chat_history_table = ddb.Table(
            self,
            f"{self.stack_name}-chat-history",
            table_name=f"{self.stack_name}-chat-history",
            partition_key=ddb.Attribute(
                name="SessionId", type=ddb.AttributeType.STRING),
            table_class=ddb.TableClass.STANDARD,
            billing_mode=ddb.BillingMode("PAY_PER_REQUEST"),
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )

        self.prompts_table = ddb.Table(
            self,
            f"{self.stack_name}-prompt-db",
            # table_name=f"{self.stack_name}-prompts-db",
            partition_key=ddb.Attribute(
                name="user_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(
                name="prompt_id", type=ddb.AttributeType.STRING),
            table_class=ddb.TableClass.STANDARD,
            billing_mode=ddb.BillingMode("PAY_PER_REQUEST"),
            removal_policy=RemovalPolicy.DESTROY,
            point_in_time_recovery=True,
        )

    # **************** Create SNS Topic ****************
    def create_sns_topic(self):
        # Create a new KMS Key for encryption
        self.kms_key = kms.Key(
            self,
            "EmailTopicEncryptionKey",
            description="KMS key for SNS topic encryption",
            enable_key_rotation=True,  # Optional: Automatically rotates the key every year
        )

        # Create SNS Topic with server-side encryption enabled
        self.sns_topic = sns.Topic(
            self,
            "EmailTopic",
            topic_name=f"{self.stack_name}-email-topic",
            master_key=self.kms_key,  # Use the created KMS key for encryption # type: ignore
        )

    # **************** Lambda Functions ****************
    def create_lambda_functions(self):
        # ********* Bedrock *********

        self.bedrock_content_generation_lambda = _lambda.Function(
            self,
            f"{self.stack_name}-bedrock-content-generation-lambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(
                "./assets/lambda/genai/bedrock_content_generation_lambda"),
            handler="bedrock_content_generation_lambda.lambda_handler",
            function_name=f"{self.stack_name}-bedrock-content-generation-lambda",
            memory_size=3008,
            timeout=Duration.seconds(QUERY_BEDROCK_TIMEOUT),
            environment={
                "BEDROCK_REGION": self.bedrock_region,
                "BEDROCK_ROLE_ARN": str(self.bedrock_role_arn),
            },
            role=self.bedrock_content_generation_role,  # type: ignore
            layers=[
                self.layers.bedrock_compatible_sdk,  # type: ignore
            ],
        )
        self.bedrock_content_generation_lambda.add_alias(
            "Warm",
            provisioned_concurrent_executions=0,
            description="Alias used for Lambda provisioned concurrency",
        )

        # ********* Bedrock Prompt Management *********
        self.prompt_management_lambda = _lambda.Function(
            self,
            f"{self.stack_name}-prompt-management-lambda",
            runtime=_lambda.Runtime.PYTHON_3_9,
            code=_lambda.Code.from_asset(
                "./assets/lambda/db_connections/prompt_lambda"),
            handler="prompt_lambda.lambda_handler",
            function_name=f"{self.stack_name}-prompt-lambda",
            memory_size=3008,
            timeout=Duration.seconds(20),
            environment={
                "TABLE_NAME": self.prompts_table.table_name,
                "BEDROCK_REGION": self.bedrock_region
            },
            layers=[
                self.layers.bedrock_compatible_sdk,  # type: ignore
            ],
            role=self.lambda_prompt_management_role,  # type: ignore
        )
        self.prompt_management_lambda.add_alias(
            "Warm",
            provisioned_concurrent_executions=0,
            description="Alias used for Lambda provisioned concurrency",
        )

        # ********* SNS Topic Lambda *********
        self.sns_topic_lambda = _lambda.Function(
            self,
            f"{self.stack_name}-sns-topic-lambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            code=_lambda.Code.from_asset("./assets/lambda/sns_topic_lambda"),
            handler="sns_topic_lambda.lambda_handler",
            function_name=f"{self.stack_name}-sns-topic-lambda",
            memory_size=128,
            timeout=Duration.seconds(20),
            environment={
                "SNS_TOPIC_ARN": self.sns_topic.topic_arn,
            },
            role=self.sns_topic_role,  # type: ignore
        )

    # **************** IAM Permissions ****************
    def create_roles(self):
        # ********* IAM Roles *********
        self.bedrock_content_generation_role = iam.Role(
            self,
            f"{self.stack_name}-bedrock-content-generation-role",
            role_name=f"{self.stack_name}-bedrock-content-generation-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),  # type: ignore
            ),
        )
        self.lambda_prompt_management_role = iam.Role(
            self,
            f"{self.stack_name}-prompt-management-role",
            role_name=f"{self.stack_name}-prompt-management-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),  # type: ignore
            ),
        )

        self.sns_topic_role = iam.Role(
            self,
            f"{self.stack_name}-sns-topic-role",
            role_name=f"{self.stack_name}-sns-topic-role",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("lambda.amazonaws.com"),  # type: ignore
            ),
        )

        # ********* Cloudwatch *********
        # Content Gen
        cloudwatch_access_docpolicy_content_gen = iam.PolicyDocument(
            statements=[
                # Allow creating log groups at the account and region level
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogGroup"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:*"],
                ),
                # Allow creating log streams and putting log events for specific Lambda functions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/{self.stack_name}-bedrock-content-generation-lambda:*"
                    ],
                ),
            ]
        )

        cloudwatch_access_policy_content = iam.Policy(
            self,
            f"{self.stack_name}-cloudwatch-access-policy-content-gen",
            policy_name=f"{self.stack_name}-cloudwatch-access-policy-content-gen",
            document=cloudwatch_access_docpolicy_content_gen,
        )

        # Prompt Management
        cloudwatch_access_doc_policy_prompt_management = iam.PolicyDocument(
            statements=[
                # Allow creating log groups at the account and region level
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogGroup"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:*"],
                ),
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/{self.stack_name}-prompt-lambda"
                    ],
                ),
            ]
        )

        cloudwatch_access_policy_prompt_management = iam.Policy(
            self,
            f"{self.stack_name}-cloudwatch-access-policy-prompt-management",
            policy_name=f"{self.stack_name}-cloudwatch-access-policy-prompt-management",
            document=cloudwatch_access_doc_policy_prompt_management,
        )

        # SNS Topic
        cloudwatch_access_doc_sns_topic = iam.PolicyDocument(
            statements=[
                # Allow creating log groups at the account and region level
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogGroup"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:*"],
                ),
                # Allow creating log streams and putting log events for specific Lambda functions
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                    resources=[
                        f"arn:aws:logs:{Aws.REGION}:{Aws.ACCOUNT_ID}:log-group:/aws/lambda/{self.stack_name}-sns-topic-lambda:*"
                    ],
                ),
            ]
        )

        cloudwatch_access_policy_sns_topic = iam.Policy(
            self,
            f"{self.stack_name}-cloudwatch-access-policy-sns-topic",
            policy_name=f"{self.stack_name}-cloudwatch-access-policy-sns-topic",
            document=cloudwatch_access_doc_sns_topic,
        )
        self.bedrock_content_generation_role.attach_inline_policy(
            cloudwatch_access_policy_content)
        self.lambda_prompt_management_role.attach_inline_policy(
            cloudwatch_access_policy_prompt_management)
        self.sns_topic_role.attach_inline_policy(
            cloudwatch_access_policy_sns_topic)

        # ********* Bedrock Prompt Management *********
        prompt_management_docpolicy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:DeleteItem",
                        "dynamodb:UpdateItem",
                        "dynamodb:Scan",
                        "dynamodb:Query",
                    ],
                    resources=[
                        self.prompts_table.table_arn,
                    ],
                ),
                iam.PolicyStatement(
                    actions=[
                        "bedrock:CreatePrompt",
                        "bedrock:UpdatePrompt",
                        "bedrock:GetPrompt",
                        "bedrock:ListPrompts",
                        "bedrock:DeletePrompt",
                        "bedrock:CreatePromptVersion",
                        "bedrock:GetFoundationModel",
                        "bedrock:ListFoundationModels",
                        "bedrock:Converse",
                        "bedrock:ConverseStream",
                        "bedrock:TagResource",
                        "bedrock:UntagResource",
                        "bedrock:ListTagsForResource",
                        "bedrock:CreateFlow",
                        "bedrock:UpdateFlow",
                        "bedrock:GetFlow",
                        "bedrock:ListFlows",
                        "bedrock:DeleteFlow",
                        "bedrock:CreateFlowVersion",
                        "bedrock:GetFlowVersion",
                        "bedrock:ListFlowVersions",
                        "bedrock:DeleteFlowVersions",
                        "bedrock:CreateFlowAlias",
                        "bedrock:UpdateFlowAlias",
                        "bedrock:GetFlowAlias",
                        "bedrock:ListFlowAliases",
                        "bedrock:DeleteFlowAlias",
                        "bedrock:InvokeFlow",
                    ],
                    resources=["*"],
                )
            ]
        )
        prompt_management_policy = iam.Policy(
            self,
            f"{self.stack_name}-prompt_management_policy",
            policy_name=f"{self.stack_name}-prompt_management_policy",
            document=prompt_management_docpolicy,
        )
        self.lambda_prompt_management_role.attach_inline_policy(
            prompt_management_policy)
        # ********* SNS Topic *********
        sns_topic_docpolicy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    actions=["sns:Publish", "sns:Subscribe",
                             "sns:ListSubscriptionsByTopic"],
                    resources=[
                        self.sns_topic.topic_arn,
                    ],
                ),
                iam.PolicyStatement(
                    actions=["kms:GenerateDataKey", "kms:Decrypt"],
                    resources=[
                        self.kms_key.key_arn,
                    ],
                ),
            ]
        )

        sns_topic_policy = iam.Policy(
            self,
            f"{self.stack_name}-sns-topic-policy",
            policy_name=f"{self.stack_name}-sns-topic-policy",
            document=sns_topic_docpolicy,
        )
        self.sns_topic_role.attach_inline_policy(sns_topic_policy)

        # ********* Bedrock *********
        bedrock_access_docpolicy = iam.PolicyDocument(
            statements=[
                iam.PolicyStatement(
                    actions=[
                        "bedrock:ListFoundationModels",
                    ],
                    resources=["*"],
                ),
                iam.PolicyStatement(
                    actions=[
                        "bedrock:InvokeModel",
                    ],
                    resources=[
                        f"arn:aws:bedrock:{Aws.REGION}::foundation-model/*"],
                ),
            ]
        )

        bedrock_access_policy = iam.Policy(
            self,
            f"{self.stack_name}-bedrock-access-policy",
            policy_name=f"{self.stack_name}-bedrock-access-policy",
            document=bedrock_access_docpolicy,
        )
        self.bedrock_content_generation_role.attach_inline_policy(
            bedrock_access_policy)
