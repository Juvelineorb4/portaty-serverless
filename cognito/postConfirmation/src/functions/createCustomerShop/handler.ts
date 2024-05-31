import {
  DynamoDBClient,
  ScanCommand,
  PutItemCommand,
  QueryCommand,
} from "@aws-sdk/client-dynamodb";
const dynamodb = new DynamoDBClient({ region: "us-east-1" });
import { v4 as uuidv4 } from "uuid";

// variables globales
const table_dynamodb_dev = process.env.TABLE_CUSTOMERSHOP_DEV;
const table_dynamodb_prod = process.env.TABLE_CUSTOMERSHOP_PROD;
const stage = process.env.STAGE;
let table_dynamodb = table_dynamodb_dev;

if (stage === "prod") table_dynamodb = table_dynamodb_prod;

const getEmailDynamodb = async (email = "") => {
  console.log("EMAIL: ", email);
  // const params = {
  //   TableName: process.env.TABLE_CUSTOMERSHOP, // Cambia esto al nombre de tu tabla
  //   FilterExpression: "email = :email",
  //   ExpressionAttributeValues: {
  //     ":email": { S: email },
  //   },
  // };
  const params = {
    TableName: table_dynamodb, // Cambia esto al nombre de tu tabla
    IndexName: "customerShopByEmail", // Cambia esto al nombre de tu índice
    KeyConditionExpression: "email = :email",
    ExpressionAttributeValues: {
      ":email": { S: email },
    },
  };
  const command = new QueryCommand(params);
  const result = await dynamodb.send(command);
  return result;
};

const createCustomerShop = async (event): Promise<any> => {
  console.log("EVENTO: ", event);
  console.log("VARIABLES: ", {
    tableDev: table_dynamodb_dev,
    tableProd: table_dynamodb_prod,
    stage: stage,
    table: table_dynamodb,
  });
  const { triggerSource, request } = event;
  // Verificar el tipo de disparador
  if (triggerSource !== "PostConfirmation_ConfirmSignUp") {
    throw new Error("Funcion no Valida para fuente de disparo");
  }

  const fields = {
    // id: { S: uuidv4() },
    userID: { S: request.userAttributes.sub },
    owner: { S: request.userAttributes.sub },
    name: { S: request.userAttributes.name },
    email: { S: request.userAttributes.email },
    "__typename:": { S: "CustomerShop" },
    createdAt: { S: new Date().toISOString() },
    updatedAt: { S: new Date().toISOString() },
  };

  const params = {
    TableName: table_dynamodb,
    Item: fields,
  };
  try {
    const result = await dynamodb.send(new PutItemCommand(params));
    // const result = await getEmailDynamodb(request.userAttributes.email);
    console.log("RESULT: ", result);
    return event;
  } catch (error) {
    throw new Error(error);
  }
};

export { createCustomerShop };
