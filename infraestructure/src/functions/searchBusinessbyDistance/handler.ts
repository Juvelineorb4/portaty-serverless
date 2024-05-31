import { defaultProvider } from "@aws-sdk/credential-provider-node";
import { Client } from "@opensearch-project/opensearch";
import { AwsSigv4Signer } from "@opensearch-project/opensearch/aws";

const client = new Client({
  ...AwsSigv4Signer({
    region: "us-east-1",
    service: "es",
    // Must return a Promise that resolve to an AWS.Credentials object.
    // This function is used to acquire the credentials when the client start and
    // when the credentials are expired.
    // The Client will refresh the Credentials only when they are expired.
    // With AWS SDK V2, Credentials.refreshPromise is used when available to refresh the credentials.

    // Example with AWS SDK V3:
  }),
  node: "https://search-amplify-opense-1x5f2ait6r2xq-vehidze7t5vrr7zqilwduumcoe.us-east-1.es.amazonaws.com ", // OpenSearch domain URL
});

interface PROPS_PARAMS {
  km: Number;
  text: String;
}

type Coordinates = {
  lat: Number;
  lon: Number;
};

const searchBusinessByDistanceHandler = async (event): Promise<any> => {
  let distance = 10;
  const params = event.queryStringParameters;
  const { location, km, text, from = 0, limit = 26 } = params;
  const { lat, lon } = JSON.parse(location);
  if (km) distance = km;

  const queryAll = {
    from: from,
    size: limit,
    query: {
      bool: {
        must: [{ match_all: {} }],
        filter: [
          {
            geo_distance: {
              distance: `${distance}km`,
              coordinates: {
                lat,
                lon,
              },
            },
          },
        ],
      },
    },
  };

  const queryByDistance = {
    from: from,
    size: limit,
    query: {
      bool: {
        must: [
          {
            wildcard: {
              tags: {
                value: `*${text}*`,
              },
            },
          },
        ],
        filter: [
          {
            geo_distance: {
              distance: `${distance}km`,
              coordinates: {
                lat,
                lon,
              },
            },
          },
        ],
      },
    },
  };

  let query = {};

  if (text) {
    query = queryByDistance;
  } else {
    query = queryAll;
  }
  try {
    const response = await client.search({
      index: "business",
      body: query,
    });
    console.log("RESPONSE: ", response.body.hits.hits);
    const newArray = [];
    response.body.hits.hits.forEach((item) => {
      const distanceAprox = distanceTwoPoints(
        lat,
        lon,
        item["_source"]?.coordinates?.lat,
        item["_source"]?.coordinates?.lon
      );
      console.log({
        id: item["_source"]?.id,
        distance: distanceAprox,
        activity: item["_source"]?.activity,
        name: item["_source"]?.name,
        path: item["_source"]?.image,
      });
      return newArray.push({
        id: item["_source"]?.id,
        distance: distanceAprox,
        activity: item["_source"]?.activity,
        name: item["_source"]?.name,
        thumbnail: item["_source"]?.thumbnail,
        images: item["_source"]?.images,
      });
    });
    console.log("NEW ARRAY: ", newArray);
    return {
      statusCode: 200,
      body: JSON.stringify({
        items: newArray,
        total: response.body.hits.total.value,
        limit: newArray.length,
      }),
    };
  } catch (error) {
    return {
      statusCode: 400,
      body: JSON.stringify({
        error,
      }),
    };
  }
};

const distanceTwoPoints = (
  latR: number,
  lonR: number,
  lat: number,
  lon: number
) => {
  const radioTierraKm = 6371; // Radio de la Tierra en kilómetros
  const dLat = toRadians(lat - latR);
  const dLon = toRadians(lonR - lon);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRadians(latR)) *
      Math.cos(toRadians(lat)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distancia = radioTierraKm * c;
  return distancia;
};

function toRadians(degrees: number) {
  return degrees * (Math.PI / 180);
}

export { searchBusinessByDistanceHandler };
