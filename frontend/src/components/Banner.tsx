export default function Banner() {
  return (
    <header className="w-full bg-[#1e3a4b] text-[#e6eef3]">
      <div className="mx-auto max-w-7xl px-4 py-3 sm:px-6 lg:px-8">
        <p className="text-[13px] leading-snug">
          Trained on a Hospital del Mar cohort of ~208 acute stroke patients
          (median days post-stroke = 6, IQR 4–11.5). Predictions apply to early
          rehabilitation; outside this window they are extrapolation.
          <span className="ml-1 align-top text-[10px]">*</span>
        </p>
        <p className="mt-1 text-[11px] leading-snug text-[#a8c0cd]">
          <span className="align-top">*</span> Cohort days post-stroke distribution
          (n=243): median 6, Q1/Q3 = 4 / 11.5, max 154. Soft warning fires
          beyond 30 days, where less than ~15% of the training data lies.
        </p>
      </div>
    </header>
  );
}
