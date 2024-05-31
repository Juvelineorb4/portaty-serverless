import type { AWS } from "@serverless/typescript";

import preRegister from "@functions/preRegister";
import postConfirmation from "@functions/postConfirmation";
import customMessage from "@functions/customMessage";

const serverlessConfiguration: AWS = {
  service: "portatyv2-cognito",
  frameworkVersion: "3",
  plugins: ["serverless-esbuild"],
  provider: {
    name: "aws",
    runtime: "nodejs20.x",
    stage: "${opt:stage, 'dev'}",
    environment: {
      AWS_NODEJS_CONNECTION_REUSE_ENABLED: "1",
      NODE_OPTIONS: "--enable-source-maps --stack-trace-limit=1000",
      STAGE: "${self:provider.stage}",
      COGNITO: "${self:custom.cognito.${opt:stage, self:provider.stage}}",
      ARN_COGNITO:
        "${self:custom.arn_cognito.${opt:stage, self:provider.stage}}",
      TABLE_USER: "${self:custom.table_user.${opt:stage, self:provider.stage}}",
      USER_POOL_ID:
        "${self:custom.cognito_user_pool_id.${opt:stage, self:provider.stage}}",
      ARN_TABLE_USER:
        "${self:custom.arn_table_user.${opt:stage, self:provider.stage}}",
    },
    iam: {
      role: {
        statements: [
          {
            Effect: "Allow",
            Action: ["dynamodb:PutItem"],
            Resource: ["${self:provider.environment.ARN_TABLE_USER}"],
          },
          {
            Effect: "Allow",
            Action: ["cognito-idp:AdminUpdateUserAttributes"],
            Resource: ["${self:provider.environment.ARN_COGNITO}"],
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
            pool: "${self:provider.environment.COGNITO}",
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
            pool: "${self:provider.environment.COGNITO}",
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
            pool: "${self:provider.environment.COGNITO}",
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
    table_user: {
      dev: "Users-ehid2xtqobf75gakml3qgdj45m-dev",
      prod: "Users-3phqsjzznfdxlnjnzszwzb6rjy-prod",
    },
    cognito: {
      dev: "professions-dev",
      prod: "professions-prod",
    },
    arn_cognito: {
      dev: "arn:aws:cognito-idp:us-east-1:086563672363:userpool/us-east-1_Mr2xjl1Hg",
      prod: "arn:aws:cognito-idp:us-east-1:086563672363:userpool/us-east-1_aiv5jx4kp",
    },
    cognito_user_pool_id: {
      dev: "us-east-1_Mr2xjl1Hg",
      prod: "us-east-1_aiv5jx4kp",
    },
    arn_table_user: {
      dev: "arn:aws:dynamodb:us-east-1:086563672363:table/Users-ehid2xtqobf75gakml3qgdj45m-dev",
      prod: "arn:aws:dynamodb:us-east-1:086563672363:table/Users-3phqsjzznfdxlnjnzszwzb6rjy-prod",
    },
  },
};

module.exports = serverlessConfiguration;
