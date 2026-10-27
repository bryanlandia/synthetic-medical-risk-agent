export function Banner() {
  return (
    <header className="banner" role="banner">
      <p className="notice">
        <strong>Synthetic data. Fictional disease. Not medical advice.</strong> Nothing here is about a real person or a real condition.
      </p>
      <p className="mock">
        <span className="tag">MOCK EHR</span> A demonstration page. It is not connected to any real system and does not use FHIR or any vendor&apos;s software.
      </p>
    </header>
  );
}
