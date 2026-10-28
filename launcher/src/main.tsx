import React from "react";
import ReactDOM from "react-dom/client";
import { domMax, LazyMotion, MotionConfig } from "motion/react";
import App from "./ui/App";
import { Overlay } from "./ui/Overlay";
import { isOverlay } from "./ui/overlayWindow";
import "./ui/theme.css";
import "./ui/app.css";
import "./ui/schedule/schedule.css";
import "./ui/kit.css";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    {/* Motion: loaded features once for both windows; it follows the system «reduce motion» setting */}
    <LazyMotion features={domMax} strict>
      <MotionConfig reducedMotion="user">
        {isOverlay ? <Overlay /> : <App />}
      </MotionConfig>
    </LazyMotion>
  </React.StrictMode>,
);
