import {
  CognitoIdentityProviderClient,
  AdminUpdateUserAttributesCommand,
  AdminGetUserCommand,
  ListUsersCommand,
} from "@aws-sdk/client-cognito-identity-provider";

// variables
const cognito = new CognitoIdentityProviderClient({ region: "us-east-1" });

const user_pool_id = process.env.USER_POOL_ID;

const getListUsersCognito = async (
  email = null,
  allUsers = [],
  paginationToken = null
) => {
  const input = {
    UserPoolId: process.env.USER_POOL_ID,
    AttributesToGet: ["sub", "email"],
    Limit: 60,
    PaginationToken: paginationToken,
    Filter: `email ^= "${email}"`,
  };

  const command = new ListUsersCommand(input);
  const response = await cognito.send(command);
  console.log("USERS COGNITO: ", response);
  allUsers = [...allUsers, ...response.Users];

  if (response.PaginationToken) {
    // Si hay un PaginationToken en la respuesta, haz otra petición para obtener más usuarios
    await getListUsersCognito(email, allUsers, response.PaginationToken);
  }

  return allUsers.length > 0;
};

const changeEmailHandler = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);
  const body = JSON.parse(event.body);
  console.log("BODY: ", body);
  const { username, newEmail } = body;

  try {
    // Obtener el usuario
    const getUserParams = {
      UserPoolId: user_pool_id,
      Username: username,
    };
    const user = await cognito.send(new AdminGetUserCommand(getUserParams));
    console.log("USUARIO OBTENIDO: ", user);
    // Verificar si el nuevo correo es igual al actual
    const currentEmail = user.UserAttributes.find(
      (attr) => attr.Name === "email"
    ).Value;
    if (currentEmail === newEmail) {
      return {
        statusCode: 400,
        body: JSON.stringify({
          success: false,
          message: "El nuevo correo electrónico es igual al actual.",
        }),
      };
    }
    // verificar que ese correo no este registrado ya en xognito

    const existingUser = await getListUsersCognito(newEmail);
    console.log("EXISTING USER: ", existingUser);
    if (existingUser) {
      return {
        statusCode: 400,
        body: JSON.stringify({
          success: false,
          message: "El correo electrónico ya se encuentra en uso.",
        }),
      };
    }

    // Actualizar el correo electrónico del usuario
    const updateUserParams = {
      UserPoolId: user_pool_id,
      Username: username,
      UserAttributes: [
        {
          Name: "email",
          Value: newEmail,
        },
        {
          Name: "email_verified",
          Value: "false",
        },
      ],
    };
    await cognito.send(new AdminUpdateUserAttributesCommand(updateUserParams));

    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        message: `Correo electrónico actualizado para el usuario ${username}. Se ha enviado un código de verificación al nuevo correo electrónico.`,
      }),
    };
  } catch (error) {
    console.error(error);
    return {
      statusCode: 500,
      body: JSON.stringify({
        success: false,
        message:
          "Hubo un error al actualizar el correo electrónico del usuario.",
        error: error,
      }),
    };
  }
};

export { changeEmailHandler };
