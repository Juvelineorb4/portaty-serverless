"use strict";

module.exports.thumbnailGenerator = async (event) => {
  console.log("EVENT: ", event);
  const { Records } = event;
  console.log("RECORDS: ", Records);
  return {
    statusCode: 200,
    body: JSON.stringify(event),
  };
};
