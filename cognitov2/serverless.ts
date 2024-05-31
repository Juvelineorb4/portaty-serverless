import type { AWS } from "@serverless/typescript";

import preRegister from "@functions/preRegister";
import postConfirmation from "@functions/postConfirmation";
import customMessage from "@functions/customMessage";

const serverlessConfiguration: AWS = {
  service: "cognito-professions",
  frameworkVersion: "3",
  plugins: ["serverless-esbuild"],
  provider: {
    name: "aws",
    runtime: "nodejs14.x",
    stage: "${opt:stage, 'dev'}",
    apiGateway: {
      minimumCompressionSize: 1024,
      shouldStartNameWithService: true,
    },
    environment: {
      AWS_NODEJS_CONNECTION_REUSE_ENABLED: "1",
      NODE_OPTIONS: "--enable-source-maps --stack-trace-limit=1000",
      TABLE_USERS_DEV: "Users-ehid2xtqobf75gakml3qgdj45m-dev",
      TABLE_USERS_PROD: "",
      ARN_TABLE_USERS_DEV:
        "arn:aws:dynamodb:us-east-1:086563672363:table/Users-ehid2xtqobf75gakml3qgdj45m-dev",
      ARN_TABLE_USERS_PROD: "",
      COGNITO_DEV: "professions-dev",
      COGNITO_PROD: "",
    },
    iam: {
      role: {
        statements: [
          {
            Effect: "Allow",
            Action: ["dynamodb:PutItem"],
            Resource: [
              "arn:aws:dynamodb:us-east-1:086563672363:table/Users-ehid2xtqobf75gakml3qgdj45m-dev",
            ],
          },
          {
            Effect: "Allow",
            Action: ["cognito-idp:AdminUpdateUserAttributes"],
            Resource: [
              "arn:aws:cognito-idp:us-east-1:086563672363:userpool/us-east-1_Mr2xjl1Hg",
            ],
          },
        ],
      },
    },
  },
  // import the function via paths
  functions: {
    preRegister: {
      ...preRegister,
      events: [
        {
          cognitoUserPool: {
            pool: "professions-dev",
            trigger: "PreSignUp",
            existing: true,
          },
        },
      ],
    },
    postConfirmation: {
      ...postConfirmation,
      events: [
        {
          cognitoUserPool: {
            pool: "professions-dev",
            trigger: "PostConfirmation",
            existing: true,
          },
        },
      ],
    },
    customMessage: {
      ...customMessage,
      events: [
        {
          cognitoUserPool: {
            pool: "professions-dev",
            trigger: "CustomMessage",
            existing: true,
          },
        },
      ],
    },
  },
  package: { individually: true },
  custom: {
    esbuild: {
      bundle: true,
      minify: false,
      sourcemap: true,
      exclude: ["aws-sdk"],
      target: "node14",
      define: { "require.resolve": undefined },
      platform: "node",
      concurrency: 10,
    },
  },
};

module.exports = serverlessConfiguration;
