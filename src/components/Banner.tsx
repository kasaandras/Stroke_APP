export default function Banner() {
  return (
    <header className="w-full bg-[#1e3a4b] text-[#e6eef3]">
      <div className="mx-auto max-w-7xl space-y-1.5 px-4 py-3 sm:px-6 lg:px-8">
        <p className="text-[13px] leading-snug">
          <span className="font-semibold">Predictions &amp; SHAP</span> were
          trained on a <span className="font-medium">Hospital del Mar BCN
          cohort</span> of ~208 acute stroke patients receiving standard
          inpatient rehabilitation — physiotherapy with occasional speech and
          language therapy — at median 6 days post-stroke (IQR 4–11.5).
          They assume similar care and timing; outside this window they are
          extrapolation.
          <span className="ml-1 align-top text-[10px]">*</span>
        </p>
        <p className="text-[13px] leading-snug">
          <span className="font-semibold">Treatments</span> surface
          observational evidence from <span className="font-medium">SCOAR
          meta-analytic trial arms</span> — published rehabilitation trials,
          NOT BCN patients. Rankings reflect average gait change reported in
          trials of similar severity, age, and chronicity; they do not predict
          this patient&apos;s outcome.
        </p>
        <p className="text-[11px] leading-snug text-[#a8c0cd]">
          <span className="align-top">*</span> BCN cohort days post-stroke
          distribution (n=243): median 6, Q1/Q3 = 4 / 11.5, max 154. Soft
          warning fires beyond 30 days, where less than ~15 % of the training
          data lies.
        </p>
      </div>
    </header>
  );
}
