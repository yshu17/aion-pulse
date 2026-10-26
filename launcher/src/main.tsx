import React from "react";
import ReactDOM from "react-dom/client";
import App from "./ui/App";
import { Overlay } from "./ui/Overlay";
import { isOverlay } from "./ui/overlayWindow";
import "./ui/theme.css";
import "./ui/app.css";
import "./ui/schedule/schedule.css";
import "./ui/kit.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {isOverlay ? <Overlay /> : <App />}
  </React.StrictMode>,
);
