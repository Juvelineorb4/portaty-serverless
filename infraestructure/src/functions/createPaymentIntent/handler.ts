const stripe = require("stripe")("sk_test_51Mr0b4ATCZIkEkhBq4eBKFBrH3DoIADWs5PZEulnKyvK8V1LGgu53AktpkLvkVLOTHCXFXWpH9jydae6cFJERdae000rSRszqv")


const createPaymentIntent = async (event): Promise<any> => {


  const { body } = event;
  const { amount } = JSON.parse(body);
  try {
    const paymentIntent = await stripe.paymentIntents.create({
      amount,
      currency: "usd",
      automatic_payment_methods: {
        enabled: true
      }
    });
    console.log("PAYMENT", paymentIntent);
    return {
      statusCode: 200,
      body: JSON.stringify({
        amount,
        secret: paymentIntent.client_secret,
        paymentID: paymentIntent.id
      })
    };
  } catch (error) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        error
      })
    };
  }



};

export { createPaymentIntent }
