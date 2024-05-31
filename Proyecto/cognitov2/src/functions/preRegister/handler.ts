const preRegisterHandler = async (event): Promise<any> => {
  console.log("EVENTO PARA VER: ", event);
  return event;
};

export { preRegisterHandler };
