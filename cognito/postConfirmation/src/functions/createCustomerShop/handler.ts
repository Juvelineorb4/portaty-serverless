import { DynamoDBClient, PutItemCommand } from '@aws-sdk/client-dynamodb'
const dynamodb = new DynamoDBClient({ region: "us-east-1" });

const createCustomerShop = async (event): Promise<any> => {
  // informacion del usuario 
  // const { userPoolId, userName } = event
  const { userAttributes } = event.request;
  const { sub, name, email } = userAttributes
  console.log(event)

  // formato del usuario 
  const fields = {
    userID: { S: sub },
    owner: { S: sub },
    name: { S: name },
    email: { S: email },
    "__typename:": { S: "CustomerShop" },
    createdAt: { S: new Date().toISOString() },
    updatedAt: { S: new Date().toISOString() }
  }

  // parametros para la carga de informacion en la tabl
  const params = {
    TableName: process.env.TABLE_CUSTOMERSHOP,
    Item: fields
  }
  try {
    const result = await dynamodb.send(new PutItemCommand(params))
    console.log("RESULT: ", result)
    return event
  } catch (error) {
    throw new Error(error)
  }


};

export { createCustomerShop }
