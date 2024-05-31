import type { AWS } from "@serverless/typescript";

import createPaymentIntent from "@functions/createPaymentIntent";
import searchBusinessbyDistance from "@functions/searchBusinessbyDistance";
const serverlessConfiguration: AWS = {
  service: "portaty",
  frameworkVersion: "3",
  plugins: ["serverless-esbuild"],
  provider: {
    name: "aws",
    runtime: "nodejs14.x",
    apiGateway: {
      minimumCompressionSize: 1024,
      shouldStartNameWithService: true,
    },
    environment: {
      AWS_NODEJS_CONNECTION_REUSE_ENABLED: "1",
      NODE_OPTIONS: "--enable-source-maps --stack-trace-limit=1000",
    },
    iam: {
      role: {
        statements: [
          {
            Effect: "Allow",
            Action: ["es:ESHttpPost"],
            Resource: [
              "arn:aws:es:us-east-1:086563672363:domain/amplify-opense-1x5f2ait6r2xq/*",
            ],
          },
        ],
      },
    },
  },
  // import the function via paths
  functions: {
    createPaymentIntent,
    searchBusinessbyDistance,
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
