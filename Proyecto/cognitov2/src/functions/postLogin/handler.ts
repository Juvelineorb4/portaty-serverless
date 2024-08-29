import {
  PutItemCommand,
  DynamoDBClient,
  UpdateItemCommand,
} from "@aws-sdk/client-dynamodb";
import {
  CognitoIdentityProviderClient,
  AdminUpdateUserAttributesCommand,
} from "@aws-sdk/client-cognito-identity-provider";

// variables
const dynamodb = new DynamoDBClient({ region: "us-east-1" });
const cognito = new CognitoIdentityProviderClient({ region: "us-east-1" });
const table_dynamodb_dev = process.env.TABLE_USER;
const user_pool_id = process.env.USER_POOL_ID;

const postLoginHandler = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);
  const { triggerSource, request } = event;

  if (triggerSource !== "PostAuthentication_Authentication") {
    console.error("LAMBDA NO DISPONIBLE PARA ESTE DISPARADOR");
    return event;
  }

  if (!request?.clientMetadata) return event;

  const { userAttributes, clientMetadata } = request;
  const { "custom:notificationToken": userNotificationToken } = userAttributes;
  const { notificationToken: clientNotificationToken } = clientMetadata;
  const { "custom:userTableID": userTableID } = userAttributes;

  if (userNotificationToken !== clientNotificationToken) {
    try {
      // Actualizar en Cognito
      const response = await updateAttributesUser(
        request,
        clientNotificationToken
      );
      console.log("RESPUESTA DE COGNITO: ", response);
    } catch (error) {
      console.error("Error actualizando atributos en Cognito: ", error);
    }

    try {
      // Actualizar en DynamoDB
      console.log("PARA DB ID:", userTableID);
      console.log("PARA DB TOKEN:", clientNotificationToken);
      const resultDB = await updateDynamoDB(
        userTableID,
        clientNotificationToken
      );
      console.log("RESULT DB: ", resultDB);
    } catch (error) {
      console.error("Error actualizando DynamoDB: ", error);
    }
  }

  return event;
};

const updateAttributesUser = async (request, token) => {
  const command = new AdminUpdateUserAttributesCommand({
    UserPoolId: user_pool_id,
    Username: request.userAttributes.email,
    UserAttributes: [
      {
        Name: "custom:notificationToken",
        Value: token,
      },
    ],
  });
  const response = await cognito.send(command);
  return response;
};

const updateDynamoDB = async (userTableID, notificationToken) => {
  const params = {
    TableName: table_dynamodb_dev,
    Key: {
      id: { S: userTableID },
    },
    UpdateExpression: "SET notificationToken = :token",
    ExpressionAttributeValues: {
      ":token": { L: [{ S: notificationToken }] },
    },
  };

  const response = await dynamodb.send(new UpdateItemCommand(params));
  console.log("Elemento actualizado en DynamoDB:", params);

  // Puedes agregar más lógica aquí si es necesario

  return response;
};

export { postLoginHandler };
