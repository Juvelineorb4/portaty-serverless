import { PutItemCommand, DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  CognitoIdentityProviderClient,
  AdminUpdateUserAttributesCommand,
} from "@aws-sdk/client-cognito-identity-provider";
import { v4 as uuidv4 } from "uuid";

// variables
const dynamodb = new DynamoDBClient({ region: "us-east-1" });
const cognito = new CognitoIdentityProviderClient({ region: "us-east-1" });
const table_dynamodb_dev = process.env.TABLE_USER;
const user_pool_id = process.env.USER_POOL_ID;

const createTableUser = async (request) => {
  const gender = request?.userAttributes["custom:gender"]
    ? request?.userAttributes["custom:gender"]
    : "";
  const notificationToken = request?.userAttributes["custom:notificationToken"]
    ? request?.userAttributes["custom:notificationToken"]
    : "";
  const name = request?.userAttributes?.name
    ? request?.userAttributes?.name
    : "";
  const lastName = request?.userAttributes["custom:lastName"]
    ? request?.userAttributes["custom:lastName"]
    : "";
  const email = request?.userAttributes?.email
    ? request?.userAttributes?.email
    : "";
  const ID = uuidv4();
  const fields = {
    id: { S: ID },
    cognitoID: { S: request.userAttributes.sub },
    owner: { S: request.userAttributes.sub },
    name: { S: name },
    lastName: { S: lastName },
    email: { S: email },
    gender: { S: gender },
    notificationToken: {
      L: [
        {
          S: notificationToken,
        },
      ],
    },

    "__typename:": { S: "Users" },
    createdAt: { S: new Date().toISOString() },
    updatedAt: { S: new Date().toISOString() },
  };

  const params = {
    TableName: table_dynamodb_dev,
    Item: fields,
  };
  const result = await dynamodb.send(new PutItemCommand(params));
  return { tableID: ID, result };
};

const updateAttributesUser = async (request, tableID) => {
  const command = new AdminUpdateUserAttributesCommand({
    UserPoolId: user_pool_id,
    Username: request.userAttributes.email,
    UserAttributes: [
      {
        Name: "custom:userTableID",
        Value: tableID,
      },
    ],
  });
  const response = await cognito.send(command);
  return response;
};

const postConfirmationHandler = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);

  const { triggerSource, request } = event;

  try {
    if (triggerSource === "PostConfirmation_ConfirmForgotPassword")
      return event;
    // crear tabla usuario
    const { tableID, result } = await createTableUser(request);
    // agregar id de tabla usuario a atributos de usuario
    console.log("RESULT TABLE USER: ", { tableID, result });
    const response = await updateAttributesUser(request, tableID);
    console.log("RESULT UPDATE ATTRIBUTES: ", response);
    return event;
  } catch (error) {
    throw new Error(error);
  }
};

export { postConfirmationHandler };
