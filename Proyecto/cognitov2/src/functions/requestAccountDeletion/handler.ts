import nodemailer from "nodemailer";
import {
  CognitoIdentityProviderClient,
  AdminGetUserCommand,
} from "@aws-sdk/client-cognito-identity-provider";

// variables
const cognito = new CognitoIdentityProviderClient({ region: "us-east-1" });

const user_pool_id = process.env.USER_POOL_ID;
const requestAccountDeletion = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);
  const params = event["queryStringParameters"];
  if (!params) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        success: false,
        message: "Ocurrio Un error con los parametros",
      }),
    };
  }
  const username = params["username"];

  if (!username) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        success: false,
        message: "Ocurrio Un error con el id",
      }),
    };
  }

  try {
    // Obtener el usuario
    const getUserParams = {
      UserPoolId: user_pool_id,
      Username: username,
    };
    const user = await cognito.send(new AdminGetUserCommand(getUserParams));
    console.log("USUARIO OBTENIDO: ", user);
    const emailAttribute = user.UserAttributes.find(
      (attribute) => attribute.Name === "email"
    ).Value;
    const subAttribute = user.UserAttributes.find(
      (attribute) => attribute.Name === "sub"
    ).Value;
    const nameAttribute = user.UserAttributes.find(
      (attribute) => attribute.Name === "name"
    ).Value;
    const lastNameAttribute = user.UserAttributes.find(
      (attribute) => attribute.Name === "custom:lastName"
    ).Value;
    const userTableIDAttribute = user.UserAttributes.find(
      (attribute) => attribute.Name === "custom:userTableID"
    ).Value;
    await sendEmail(emailAttribute);
    await sendEmailToPortaty(
      subAttribute,
      nameAttribute,
      lastNameAttribute,
      userTableIDAttribute,
      emailAttribute
    );
    return {
      statusCode: 200,
      body: JSON.stringify({
        success: true,
        message:
          "Tu Solicitud para eliminar tu cuenta a sido enviada, esto podria tardar 30 dias habiles!",
      }),
    };
  } catch (error) {
    return {
      statusCode: 500,
      body: JSON.stringify({
        success: false,
        message: "Ocurrio un error al solicitar eliminar tu cuenta",
        error: error,
      }),
    };
  }
};

async function sendEmail(des) {
  let remitente = "no-responder@portaty.com";
  let destinatario = des;
  let mensaje = "Esta solicitud podria tardar 30 dias habiltes!";

  let transporter = nodemailer.createTransport({
    host: "smtp.zoho.com",
    port: 465,
    secure: true, // true for 465, false for other ports
    auth: {
      user: remitente,
      pass: "HdCmgawsJZbN", // Utiliza variables de entorno o un sistema de gestión de secretos
    },
  });

  let mailOptions = {
    from: remitente,
    to: destinatario,
    subject: "Tu solicitud para eliminar tu cuenta en PORTATY a sido enviada!",
    text: mensaje,
  };

  try {
    let info = await transporter.sendMail(mailOptions);
    console.log("Message sent: %s", info.messageId);
  } catch (error) {
    console.log("Error al enviar el correo electrónico:", error);
  }
}

async function sendEmailToPortaty(sub, name, lastname, tableid, email) {
  let remitente = "no-responder@portaty.com";
  let destinatario = "admin@portaty.com";
  const htmlTemplate = `
  <h1>El Usuario ${name} ${lastname} (${sub})</h1>
  <p>Estimado equipo,</p>
  <p>El Usuario <strong>${name} ${lastname} (${sub})</strong> ha solicitado eliminar sus datos de portaty.</p>
  <h2>Detalles del Usuario:</h2>
  <ul>
    <li>Usuario: ${name} ${lastname}</li>
    <li>Correo: ${email}</li>
    <li>Cognito ID: ${sub}</li>
    <li>Table Business ID: ${tableid}</li>
  </ul>
  `;

  let transporter = nodemailer.createTransport({
    host: "smtp.zoho.com",
    port: 465,
    secure: true, // true for 465, false for other ports
    auth: {
      user: remitente,
      pass: "HdCmgawsJZbN", // Utiliza variables de entorno o un sistema de gestión de secretos
    },
  });

  let mailOptions = {
    from: remitente,
    to: destinatario,
    subject: `El usuario ${sub} ha solicitado eliminar su cuenta en Portaty.`,
    html: htmlTemplate,
  };

  try {
    let info = await transporter.sendMail(mailOptions);
    console.log("Message sent: %s", info.messageId);
  } catch (error) {
    console.log("Error al enviar el correo electrónico:", error);
  }
}

export { requestAccountDeletion };
