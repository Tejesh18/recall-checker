export default function HowTo() {
  return (
    <section className="howto">
      <h2>Getting your Amazon order history</h2>
      <ol>
        <li>
          Go to{" "}
          <a href="https://www.amazon.com/hz/privacy-central/data-requests/preview.html" target="_blank" rel="noreferrer">
            Request Your Data
          </a>{" "}
          on Amazon.
        </li>
        <li>
          Pick <b>Your Orders</b> and submit. Amazon emails you to confirm, then again when it's ready. That part
          usually takes a day or two.
        </li>
        <li>Download the zip and drop it above as is. No need to unzip it.</li>
      </ol>
      <p className="small">
        Not on Amazon? Export a spreadsheet of what you bought, or just type product names in a column called
        "Item" and save it as CSV.
      </p>
    </section>
  );
}
