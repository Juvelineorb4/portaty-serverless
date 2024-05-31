'use strict';
const complaintTypes = [
  "Desnudos",
  "Trastorno alimenticio",
  "Relacionado con un menor",
  "Acoso",
  "Violencia",
  "Spam",
  "Suicidio o autolesiones",
  "Ventas no autorizadas",
  "Información falsa",
  "Lenguaje que incita al odio",
  "Fraude",
  "Terrorismo",
];

module.exports.handler = async () => {
  return {
    statusCode: 200,
    body: JSON.stringify(complaintTypes),
  };
};
