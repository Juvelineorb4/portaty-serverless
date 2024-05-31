import { handlerPath } from "@libs/handler-resolver";

export default {
  handler: `${handlerPath(__dirname)}/handler.searchBusinessByDistanceHandler`,
  events: [
    {
      http: {
        path: "searchBusinessByDistance",
        method: "get",
      },
    },
  ],
};
