import {
  CognitoIdentityProviderClient,
  ListUsersCommand,
} from "@aws-sdk/client-cognito-identity-provider";

import { Expo } from "expo-server-sdk";
import axios, { all } from "axios";

// variables
const cognito = new CognitoIdentityProviderClient({ region: "us-east-1" });

const user_pool_id = process.env.USER_POOL_ID;
const appsync_url = process.env.APPSYNC_URL;
const appsync_api_key = process.env.APPSYNC_API_KEY;

const getListUsersCognito = async (allUsers = [], paginationToken = null) => {
  const input = {
    UserPoolId: user_pool_id,
    PaginationToken: paginationToken,
  };

  const command = new ListUsersCommand(input);
  const response = await cognito.send(command);
  console.log("USUARIOS ENTRANTES: ", response.Users.length);
  allUsers.push(...response.Users);
  console.log("COMO QUEDA: ", allUsers);
  console.log("PAFA VER: ", allUsers.length);
  if (response.PaginationToken) {
    console.log("PAGINATION: ", response.PaginationToken);
    // Si hay un PaginationToken en la respuesta, haz otra petición para obtener más usuarios
    await getListUsersCognito(allUsers, response.PaginationToken);
  }

  return allUsers;
};

const createNotificationHistory = async (title = "", message = "") => {
  const axios = require("axios");

  const mutation = `
     mutation CreateNotificationHistory(
    $input: CreateNotificationHistoryInput!
   
  ) {
    createNotificationHistory(input: $input) {
      id
      title
      message
      createdAt
      updatedAt
      __typename
    }
  }
  `;

  const variables = {
    input: {
      title,
      message,
    },
  };

  const headers = {
    "Content-Type": "application/json",
    "x-api-key": appsync_api_key, // Utiliza la clave API en la cabecera x-api-key
  };

  const result = await axios.post(
    appsync_url,
    {
      query: mutation,
      variables: variables,
    },
    {
      headers: headers,
    }
  );
  console.log(result.data);
};
const sendPushNotificationsHandler = async (event): Promise<any> => {
  const notificationPromises = [];
  const body = JSON.parse(event.body);
  const { title, message } = body;

  if (!title || !message) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        success: false,
        message: "Faltan parámetros en el body",
      }),
    };
  }

  try {
    const allUsers = await getListUsersCognito();
    console.log("CANTIDAD DE USUARIOS: ", allUsers?.length);
    // armar mensajes
    const messages = allUsers
      .map((user) => {
        const notificationToken = user.Attributes.find(
          (attr) => attr.Name === "custom:notificationToken"
        );
        return notificationToken
          ? {
              to: notificationToken.Value,
              title: title,
              body: message,
            }
          : null;
      })
      .filter((msg) => msg !== null);
    console.log("CANTIDAD DE MENSAJES: ", messages.length);
    // Enviar todos los mensajes notificaciones
    for (const msg of messages) {
      const notification = {
        ...msg,
      };

      const promise = (async () => {
        try {
          // Push notifications are sent to Expo's servers. Expo then forwards the notification to either Apple or Android
          // notification servers.
          // Diagram: https://docs.expo.dev/static/images/sending-notification.png
          await axios.post(
            "https://exp.host/--/api/v2/push/send",
            notification,
            {
              headers: {
                Accept: "application/json",
                "Accept-encoding": "gzip, deflate",
                "Content-Type": "application/json",
              },
            }
          );
          return `Push notification successfully sent to '${notification.to}' via Expo's Push API.`;
        } catch (error) {
          // Most common error is due to invalid push tokens, such as "", null, or undefined.
          return `Error sending push notification to '${notification.to}'. Is this Expo push token valid?`;
        }
      })();

      notificationPromises.push(promise);
    }
    // // fesultados de envio de ntoficiaciones
    const results = await Promise.all(notificationPromises);
    console.log("RESULTS: ", results);
    // // guardar historico de notificion
    await createNotificationHistory(title, message);
    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        message: "Mensajes Enviados con exito",
      }),
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({
        success: false,
        message: "Ocurrio un error al enviar los mensajes",
        error: error,
      }),
    };
  }
};
export { sendPushNotificationsHandler };
