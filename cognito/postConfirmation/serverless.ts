import type { AWS } from '@serverless/typescript';
import createCustomerShop from '@functions/createCustomerShop'

const serverlessConfiguration: AWS = {
  service: 'postConfirmUser',
  frameworkVersion: '3',
  plugins: ['serverless-esbuild'],
  provider: {
    name: 'aws',
    runtime: 'nodejs14.x',
    // apiGateway: {
    //   restApiId: "h5920e8h3l",
    //   restApiRootResourceId: "7x80z6o7ec",
    //   minimumCompressionSize: 1024,
    //   shouldStartNameWithService: true,
    // },
    environment: {
      AWS_NODEJS_CONNECTION_REUSE_ENABLED: '1',
      NODE_OPTIONS: '--enable-source-maps --stack-trace-limit=1000',
      TABLE_CUSTOMERSHOP: "CustomerShop-zajoupn5szdfjfucr7vavz63u4-dev",
      ARN_TABLE_CUSTOMERSHOP: "arn:aws:dynamodb:us-east-1:086563672363:table/CustomerShop-zajoupn5szdfjfucr7vavz63u4-dev"
    },
    iam: {
      role: {
        statements: [
          {
            Effect: "Allow",
            Action: ["dynamodb:PutItem"],
            Resource: [
              "arn:aws:dynamodb:us-east-1:086563672363:table/CustomerShop-zajoupn5szdfjfucr7vavz63u4-dev"
            ]
          },
          {
            "Effect": "Allow",
            "Action": [
              "cognito-idp:AdminGetUser",
              "cognito-identity:GetCredentialsForIdentity"
            ],
            "Resource": [
              "arn:aws:cognito-idp:us-east-1:086563672363:userpool/us-east-1_xrukmGZfB"
            ]
          }
        ]
      }
    }
  },
  // import the function via paths
  functions: {
    createCustomerShop: {
      ...createCustomerShop,
      events: [
        {
          "cognitoUserPool": {
            "pool": "portaty-dev",
            "trigger": "PostConfirmation",
            "existing": true
          }
        }
      ]
    }
  },
  package: { individually: true },
  custom: {
    esbuild: {
      bundle: true,
      minify: false,
      sourcemap: true,
      exclude: ['aws-sdk'],
      target: 'node14',
      define: { 'require.resolve': undefined },
      platform: 'node',
      concurrency: 10,
    },
  },
};

module.exports = serverlessConfiguration;
