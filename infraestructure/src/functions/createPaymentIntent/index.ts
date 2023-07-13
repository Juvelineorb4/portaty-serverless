import { handlerPath } from '@libs/handler-resolver';

export default {
  handler: `${handlerPath(__dirname)}/handler.createPaymentIntent`,
  events: [
    {
        http: {
            path: "paymentIntent",
            method: "post",
        }
    }
]
};
