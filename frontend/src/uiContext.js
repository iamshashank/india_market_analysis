import { createContext, useContext } from "react";

// Shared UI services: toast notifications + a global "busy" indicator.
export const UIContext = createContext({
  toast: () => {},
  setBusy: () => {},
});

export const useUI = () => useContext(UIContext);
