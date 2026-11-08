import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import WalletApp from "./WalletApp";
import "../styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("No se encontró el contenedor de la aplicación.");

createRoot(root).render(
  <StrictMode>
    <WalletApp />
  </StrictMode>,
);
