const {
  CognitoIdentityProviderClient,
  AdminLinkProviderForUserCommand,
  AdminCreateUserCommand,
  AdminSetUserPasswordCommand,
  ListUsersCommand,
} = require("@aws-sdk/client-cognito-identity-provider");

// Inicializa el cliente de Cognito usando la región que especificas en tus variables de entorno
const cognitoClient = new CognitoIdentityProviderClient({
  region: process.env.AWS_REGION,
});

const preRegisterHandler = async (event): Promise<any> => {
  console.log("PreSignUp event", event);

  const { triggerSource, userPoolId, userName, request } = event;

  // Asegurarnos de que el campo 'birthdate' esté presente. Si no lo está, lo seteamos con el valor por defecto '2000-01-01'.
  if (!request.userAttributes.birthdate) {
    request.userAttributes.birthdate = "2000-01-01";
    console.log("Birthdate no presente, seteado a 2000-01-01");
  }

  // Verificamos si el signup es con un proveedor externo (por ejemplo, Google o Apple)
  if (triggerSource === "PreSignUp_ExternalProvider") {
    const { email, given_name, family_name } = request.userAttributes;

    // Buscar usuario por correo electrónico en el pool de usuarios de Cognito
    const user = await findUserByEmail(email, userPoolId);

    // Extraer nombre y valor del proveedor del userName (ej. "Google_12345")
    let [providerName, providerUserId] = userName.split("_");

    // Capitalizar la primera letra del nombre del proveedor
    providerName = providerName.charAt(0).toUpperCase() + providerName.slice(1);

    if (user) {
      // Si el usuario existe, vinculamos la cuenta federada
      await linkSocialAccount({
        userPoolId,
        cognitoUsername: user.Username,
        providerName,
        providerUserId,
      });

      return event;
    } else {
      // Si no se encuentra el usuario, creamos uno nuevo
      const newUser = await createUser({
        userPoolId,
        email,
        givenName: given_name,
        familyName: family_name,
        birthdate: "2000-01-01", // Establecemos la fecha de nacimiento por defecto
      });

      if (!newUser) {
        throw new Error("Failed to create user");
      }

      // Cambiar la contraseña para establecer el estado como CONFIRMED
      await setUserPassword({
        userPoolId,
        email,
      });

      // Vincular la cuenta federada con la cuenta creada
      await linkSocialAccount({
        userPoolId,
        cognitoUsername: newUser.Username,
        providerName,
        providerUserId,
      });

      // Configurar las respuestas para verificar y confirmar automáticamente al usuario
      event.response.autoVerifyEmail = true;
      event.response.autoConfirmUser = true;
    }
  }

  // Si el usuario se registró con correo y contraseña, no hacemos nada adicional
  return event;
};

export { preRegisterHandler };

// Función auxiliar para buscar un usuario por email en Cognito
async function findUserByEmail(email, userPoolId) {
  const command = new ListUsersCommand({
    UserPoolId: userPoolId,
    Filter: `email = "${email}"`,
    Limit: 1,
  });

  try {
    const response = await cognitoClient.send(command);
    return response.Users && response.Users.length > 0
      ? response.Users[0]
      : null;
  } catch (error) {
    console.error("Error finding user by email:", error);
    return null;
  }
}

// Función auxiliar para crear un usuario en Cognito
async function createUser({
  userPoolId,
  email,
  givenName,
  familyName,
  birthdate,
}) {
  const command = new AdminCreateUserCommand({
    UserPoolId: userPoolId,
    Username: email,
    UserAttributes: [
      { Name: "email", Value: email },
      { Name: "given_name", Value: givenName },
      { Name: "family_name", Value: familyName },
      { Name: "birthdate", Value: birthdate },
      { Name: "email_verified", Value: "true" },
    ],
    DesiredDeliveryMediums: ["EMAIL"],
  });

  try {
    const response = await cognitoClient.send(command);
    return response.User;
  } catch (error) {
    console.error("Error creating user:", error);
    return null;
  }
}

// Función auxiliar para establecer la contraseña del usuario
async function setUserPassword({ userPoolId, email }) {
  const command = new AdminSetUserPasswordCommand({
    UserPoolId: userPoolId,
    Username: email,
    Password: "TemporaryPassword123!", // Establece una contraseña temporal
    Permanent: true,
  });

  try {
    await cognitoClient.send(command);
  } catch (error) {
    console.error("Error setting user password:", error);
  }
}

// Función auxiliar para vincular una cuenta social con una cuenta de Cognito
async function linkSocialAccount({
  userPoolId,
  cognitoUsername,
  providerName,
  providerUserId,
}) {
  const command = new AdminLinkProviderForUserCommand({
    UserPoolId: userPoolId,
    DestinationUser: {
      ProviderName: "Cognito", // Cognito es el proveedor por defecto
      ProviderAttributeValue: cognitoUsername,
    },
    SourceUser: {
      ProviderName: providerName, // Google o Apple
      ProviderAttributeName: "Cognito_Subject",
      ProviderAttributeValue: providerUserId,
    },
  });

  try {
    await cognitoClient.send(command);
    console.log("Cuenta social vinculada exitosamente");
  } catch (error) {
    console.error("Error al vincular cuenta social:", error);
  }
}
