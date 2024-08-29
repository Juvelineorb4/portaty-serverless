import type { AWS } from "@serverless/typescript";

import preRegister from "@functions/preRegister";
import postConfirmation from "@functions/postConfirmation";
import customMessage from "@functions/customMessage";
import changeEmail from "@functions/changeEmail";
import requestAccountDeletion from "@functions/requestAccountDeletion";
import preAuth from "@functions/preAuth";
import sendPushNotifications from "@functions/sendPushNotifications";
import postLogin from "@functions/postLogin";
const serverlessConfiguration: AWS = {
  service: "portatyv2-cognito",
  frameworkVersion: "3",
  plugins: ["serverless-esbuild"],
  provider: {
    name: "aws",
    runtime: "nodejs20.x",
    stage: "${opt:stage, 'dev'}",
    apiGateway: {
      restApiId:
        "${self:custom.api_gateway_id.${opt:stage, self:provider.stage}}",
      restApiRootResourceId:
        "${self:custom.api_gateway_resourceid.${opt:stage, self:provider.stage}}",
    },
    environment: {
      AWS_NODEJS_CONNECTION_REUSE_ENABLED: "1",
      NODE_OPTIONS: "--enable-source-maps --stack-trace-limit=1000",
      STAGE: "${self:provider.stage}",
      COGNITO: "${self:custom.cognito.${opt:stage, self:provider.stage}}",
      APP_CLIENT_COGNITO:
        "${self:custom.app_client_cognito.${opt:stage, self:provider.stage}}",
      ARN_COGNITO:
        "${self:custom.arn_cognito.${opt:stage, self:provider.stage}}",
      TABLE_USER: "${self:custom.table_user.${opt:stage, self:provider.stage}}",
      USER_POOL_ID:
        "${self:custom.cognito_user_pool_id.${opt:stage, self:provider.stage}}",
      ARN_TABLE_USER:
        "${self:custom.arn_table_user.${opt:stage, self:provider.stage}}",
      TABLE_NOTIFICATION:
        "${self:custom.table_notification.${opt:stage, self:provider.stage}}",
      ARN_TABLE_NOTIFICATION:
        "${self:custom.arn_table_notification.${opt:stage, self:provider.stage}}",
      APPSYNC_API_KEY:
        "${self:custom.appsync_key.${opt:stage, self:provider.stage}}",
      APPSYNC_ARN:
        "${self:custom.appsync_arn.${opt:stage, self:provider.stage}}",
      APPSYNC_URL:
        "${self:custom.appsync_url.${opt:stage, self:provider.stage}}",
    },
    iam: {
      role: {
        statements: [
          {
            Effect: "Allow",
            Action: ["dynamodb:PutItem", "dynamodb:UpdateItem"],
            Resource: [
              "${self:provider.environment.ARN_TABLE_USER}",
              "${self:provider.environment.ARN_TABLE_NOTIFICATION}",
            ],
          },
          {
            Effect: "Allow",
            Action: [
              "cognito-idp:AdminUpdateUserAttributes",
              "cognito-idp:AdminGetUser",
              "cognito-idp:ConfirmSignUp",
              "cognito-idp:ResendConfirmationCode",
              "cognito-idp:ListUsers",
            ],
            Resource: ["${self:provider.environment.ARN_COGNITO}"],
          },
          {
            Effect: "Allow",
            Action: ["appsync:GraphQL"],
            Resource: ["${self:provider.environment.APPSYNC_ARN}"],
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
    changeEmail: {
      ...changeEmail,
      events: [
        {
          http: {
            path: "changeEmail",
            method: "post",
          },
        },
      ],
      timeout: 30,
    },
    requestAccountDeletion: {
      ...requestAccountDeletion,
      events: [
        {
          http: {
            path: "request_account_deletion",
            method: "get",
          },
        },
      ],
      timeout: 30,
    },
    preAuth: {
      ...preAuth,
      events: [
        {
          cognitoUserPool: {
            pool: "${self:provider.environment.COGNITO}",
            trigger: "PreAuthentication",
            existing: true,
          },
        },
      ],
    },
    postLogin: {
      ...postLogin,
      events: [
        {
          cognitoUserPool: {
            pool: "${self:provider.environment.COGNITO}",
            trigger: "PostAuthentication",
            existing: true,
          },
        },
      ],
    },
    sendPushNotifications: {
      ...sendPushNotifications,
      events: [
        {
          http: {
            path: "/dashboard/sendNotifications",
            method: "post",
          },
        },
      ],
      timeout: 30,
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
    app_client_cognito: {
      dev: "2tlmib17h4hrvampjlbl915jp9",
      prod: "",
    },
    cognito_user_pool_id: {
      dev: "us-east-1_Mr2xjl1Hg",
      prod: "us-east-1_aiv5jx4kp",
    },
    arn_table_user: {
      dev: "arn:aws:dynamodb:us-east-1:086563672363:table/Users-ehid2xtqobf75gakml3qgdj45m-dev",
      prod: "arn:aws:dynamodb:us-east-1:086563672363:table/Users-3phqsjzznfdxlnjnzszwzb6rjy-prod",
    },
    api_gateway_id: {
      dev: "x0nk2m8hvi",
      prod: "z5i64n32d6",
    },
    api_gateway_resourceid: {
      dev: "eclownm620",
      prod: "xugqzpp4pb",
    },
    table_notification: {
      dev: "NotificationHistory-ehid2xtqobf75gakml3qgdj45m-dev",
      prod: "NotificationHistory-3phqsjzznfdxlnjnzszwzb6rjy-prod",
    },
    arn_table_notification: {
      dev: "arn:aws:dynamodb:us-east-1:086563672363:table/NotificationHistory-ehid2xtqobf75gakml3qgdj45m-dev",
      prod: "arn:aws:dynamodb:us-east-1:086563672363:table/NotificationHistory-3phqsjzznfdxlnjnzszwzb6rjy-prod",
    },
    appsync_key: {
      dev: "da2-2ardlryjrvdl3cqdyrtz2ppq5i",
      prod: "da2-x4g3fxoha5eeroeswkza7fznny",
    },
    appsync_arn: {
      dev: "arn:aws:appsync:us-east-1:086563672363:apis/ehid2xtqobf75gakml3qgdj45m/types/Mutation/fields/updateBusiness",
      prod: "arn:aws:appsync:us-east-1:086563672363:apis/3phqsjzznfdxlnjnzszwzb6rjy/types/Mutation/fields/updateBusiness",
    },
    appsync_url: {
      dev: "https://vkrtsagkivgqjgzbnhekkyusfm.appsync-api.us-east-1.amazonaws.com/graphql",
      prod: "https://cq6hw4g7arg4jitnxitbhihhpu.appsync-api.us-east-1.amazonaws.com/graphql",
    },
  },
};

module.exports = serverlessConfiguration;
