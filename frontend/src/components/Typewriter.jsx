import React, { useEffect, useState } from "react";

// Types out `text` one character at a time, with a blinking caret.
export default function Typewriter({ text, speed = 16, className }) {
  const [n, setN] = useState(0);

  useEffect(() => {
    setN(0);
    if (!text) return undefined;
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setN(i);
      if (i >= text.length) clearInterval(id);
    }, speed);
    return () => clearInterval(id);
  }, [text, speed]);

  const done = n >= (text ? text.length : 0);

  return (
    <span className={className}>
      {text ? text.slice(0, n) : ""}
      <span className={"caret" + (done ? " caret--rest" : "")} aria-hidden="true" />
    </span>
  );
}
