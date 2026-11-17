import { useRef, useState } from "react";

interface Props {
  ready: boolean;
  onFile: (f: File) => void;
  onSample: () => void;
}

export default function DropZone({ ready, onFile, onSample }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);

  return (
    <div
      className={`drop ${over ? "over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files[0];
        if (f && ready) onFile(f);
      }}
    >
      <p>
        Drop <code>Your Orders.zip</code> or <code>Retail.OrderHistory.1.csv</code> here
      </p>
      <div className="buttons">
        <button disabled={!ready} onClick={() => input.current?.click()}>
          {ready ? "Choose file" : "Loading recalls..."}
        </button>
        <button className="secondary" disabled={!ready} onClick={onSample}>
          Try a sample order history
        </button>
      </div>
      <p className="small">Any CSV with a product name column works too (Walmart, Target, a list you typed up).</p>
      <input
        ref={input}
        type="file"
        accept=".csv,.zip"
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
