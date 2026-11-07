// The small credit under the content: who made it, for which server and the version of this release (read from the
// program itself; the plain browser page has no program and shows the credit alone).
import { useEffect, useState } from "react";

import { platform } from "./platform";

export function Credit() {
  const [version, setVersion] = useState("");
  useEffect(() => {
    platform?.updateStatus().then((status) => setVersion(status.version)).catch(() => {});
  }, []);
  return <div className="credit" aria-hidden="true">Developed by Sexbomb, special for Aion Empire{version && ` · v${version}`}</div>;
}
