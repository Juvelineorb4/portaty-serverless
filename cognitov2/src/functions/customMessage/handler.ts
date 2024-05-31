const customMessageHandler = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);
  return event;
};

export { customMessageHandler };
