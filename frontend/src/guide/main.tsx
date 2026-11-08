import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import GuideApp from "./GuideApp";
import "../styles.css";

const root = document.getElementById("root");
if (!root) throw new Error("No se encontró el contenedor de la guía.");

createRoot(root).render(
  <StrictMode>
    <GuideApp />
  </StrictMode>,
);
