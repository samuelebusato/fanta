import { nearestAuctionPrice } from "./auction-state.js";
import { Disclosure, RoleChip } from "./ui.jsx";

export const RECOMMENDATION_LABELS = {
  STRONG_BUY: "Ottimo prezzo",
  BID: "Prezzo corretto",
  VALUE_ONLY: "Solo al prezzo giusto",
  PASS: "Lascia andare",
  INELIGIBLE: "Non acquistabile",
};

export const PURPOSE_LABELS = {
  STARTER: "Titolare",
  ROTATION: "Rotazione",
  HANDCUFF: "Copertura della stessa squadra",
  COVERAGE: "Copertura",
  DEPTH: "Nessun beneficio per la rosa",
  NO_FIT: "Non migliora il piano rosa",
  INACTIVE: "Non disponibile",
};

export const RECOMMENDATION_TONE = {
  STRONG_BUY: "go",
  BID: "go",
  VALUE_ONLY: "warn",
  PASS: "stop",
  INELIGIBLE: "stop",
};

export const BID_STEPS = [-5, -1, 1, 5];

const clampPercent = (value) => Math.max(0, Math.min(100, value));

export const recommendationLabel = (advice) =>
  RECOMMENDATION_LABELS[advice?.recommendation] || "Valuta";

export const purposeLabel = (advice) =>
  PURPOSE_LABELS[advice?.purpose] || "Valuta per la rosa";

export const bidVerdict = ({ advice, price, rules, legalMax }) => {
  const value = Number(price);
  const hasPrice = Number.isFinite(value) && value > 0;
  const maxBid = Number(advice?.maxBid ?? 0);
  const idealMax = Number(advice?.idealMax ?? 0);
  const unaffordable = maxBid < rules.auction.minPrice;
  const priceTone = unaffordable
    ? "stop"
    : value > legalMax || value > maxBid
      ? "stop"
      : value > idealMax
        ? "warn"
        : "go";
  const recommendation = recommendationLabel(advice);
  const purpose = purposeLabel(advice);
  return {
    value,
    hasPrice,
    unaffordable,
    recommendation,
    purpose,
    tone: !advice
      ? null
      : hasPrice
        ? priceTone
        : RECOMMENDATION_TONE[advice.recommendation] || null,
    headline: !advice
      ? "Calcolo…"
      : unaffordable
        ? "Non acquistabile"
        : !hasPrice
          ? purpose
          : value > legalMax
            ? "Fuori budget"
            : value > maxBid
              ? "Troppo caro"
              : value > idealMax
                ? "Ancora accettabile"
                : purpose,
  };
};

export function BidGauge({ advice, price, rules, legalMax }) {
  const { value, hasPrice } = bidVerdict({ advice, price, rules, legalMax });
  const maxBid = Number(advice?.maxBid ?? 0);
  if (!advice || maxBid < rules.auction.minPrice) return null;
  const market = Number(advice.summary?.estimatedMarketPrice);
  const idealMin = Number(advice.idealMin ?? 0);
  const idealMax = Number(advice.idealMax ?? 0);
  const anchor = Math.max(
    maxBid,
    Number.isFinite(market) ? market : 0,
    hasPrice ? value : 0,
    rules.auction.minPrice,
  );
  const scale = Math.max(anchor * 1.25, anchor + 4);
  const pct = (input) => clampPercent((input / scale) * 100);

  return (
    <div className="gauge">
      <div
        className="gauge-track"
        style={{
          "--ideal-start": `${pct(idealMin)}%`,
          "--ideal-width": `${Math.max(0, pct(idealMax) - pct(idealMin))}%`,
          "--now": `${hasPrice ? pct(value) : 0}%`,
        }}
      >
        <span className="gauge-fill" />
        <span className="gauge-band" />
        {Number.isFinite(market) ? (
          <span
            className="gauge-mark gauge-mark--market"
            style={{ "--at": `${pct(market)}%` }}
          />
        ) : null}
        <span
          className="gauge-mark gauge-mark--cap"
          style={{ "--at": `${pct(maxBid)}%` }}
        />
        {hasPrice ? (
          <span className="gauge-thumb" style={{ "--now": `${pct(value)}%` }}>
            {value}
          </span>
        ) : null}
      </div>
      <div className="gauge-legend">
        <span>
          <i className="k-band" />
          ideale{" "}
          <b>
            {idealMin}–{idealMax}
          </b>
        </span>
        <span>
          <i className="k-cap" />
          non superare <b>{maxBid}</b>
        </span>
        {Number.isFinite(market) ? (
          <span>
            <i className="k-market" />
            mercato <b>{market}</b>
          </span>
        ) : null}
      </div>
    </div>
  );
}

export function PriceStepper({
  price,
  rules,
  legalMax,
  onPrice,
  onSubmit,
  inputRef,
}) {
  const bump = (steps) => {
    const current = nearestAuctionPrice(price, legalMax, rules);
    if (current == null) return;
    const next = nearestAuctionPrice(
      current + steps * rules.auction.increment,
      legalMax,
      rules,
    );
    if (next != null) onPrice(String(next));
  };

  return (
    <div className="stepper">
      {BID_STEPS.slice(0, 2).map((step) => (
        <button
          key={step}
          type="button"
          onClick={() => bump(step)}
          aria-label={`Riduci di ${Math.abs(step * rules.auction.increment)}`}
        >
          {step * rules.auction.increment}
        </button>
      ))}
      <input
        ref={inputRef}
        className="input"
        type="number"
        inputMode="numeric"
        min={rules.auction.minPrice}
        max={legalMax}
        step={rules.auction.increment}
        value={price}
        onChange={(event) => onPrice(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && onSubmit()}
        placeholder="Prezzo"
        aria-label="Prezzo di acquisto in crediti"
      />
      {BID_STEPS.slice(2).map((step) => (
        <button
          key={step}
          type="button"
          onClick={() => bump(step)}
          aria-label={`Aumenta di ${step * rules.auction.increment}`}
        >
          +{step * rules.auction.increment}
        </button>
      ))}
    </div>
  );
}

export function AdviceDetail({ advice, player }) {
  if (!advice) return null;
  return (
    <div className="verdict-more">
      <Disclosure summary="Perché" badge={`${advice.reasons.length}`}>
        <ul className="bullets">
          {advice.reasons.slice(0, 4).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      </Disclosure>
      <Disclosure
        summary="Attenzione"
        badge={advice.risks.length ? `${advice.risks.length}` : "0"}
      >
        {advice.risks.length ? (
          <ul className="bullets bullets--warn">
            {advice.risks.slice(0, 4).map((risk) => (
              <li key={risk}>{risk}</li>
            ))}
          </ul>
        ) : (
          <p className="micro">Nessun rischio specifico rilevato.</p>
        )}
      </Disclosure>
      {advice.alternatives.length ? (
        <Disclosure
          summary="Alternative nello stesso ruolo"
          badge={`${advice.alternatives.length}`}
        >
          <div className="rows">
            {advice.alternatives.map((alternative) => (
              <div className="row" key={alternative.id}>
                <RoleChip role={alternative.role} />
                <span className="row-main">
                  <span className="row-title">{alternative.name}</span>
                  <span className="row-sub">
                    differenza di valore {alternative.valueGap}
                  </span>
                </span>
                <span className="row-value">≈ {alternative.estimatedCost}</span>
              </div>
            ))}
          </div>
        </Disclosure>
      ) : null}
      <ContestoAllenatore contesto={player?.contesto_allenatore} />
    </div>
  );
}

/**
 * NOSTRO — non fa parte di fishertiger originale (vedi ../../FONTE.md).
 *
 * fishertiger proietta il rendimento individuale ma ignora chi allena. Qui
 * entrano il contesto di squadra e le statistiche avanzate: il moltiplicatore
 * con il suo segno, i motivi in parole (un numero senza il perche' non e'
 * utilizzabile all'asta) e lo scarto fra gol e occasioni create.
 */
function ContestoAllenatore({ contesto }) {
  if (!contesto) return null;
  const moltiplicatore = contesto.moltiplicatore ?? 1;
  const percentuale = Math.round((moltiplicatore - 1) * 100);
  const favorevole = percentuale > 2;
  const sfavorevole = percentuale < -2;
  const avanzate = contesto.avanzate;
  return (
    <Disclosure
      summary="Contesto allenatore"
      badge={`${percentuale > 0 ? "+" : ""}${percentuale}%`}
    >
      <p className="micro">
        {contesto.allenatore ?? "allenatore non noto"}
        {contesto.modulo ? ` · ${contesto.modulo}` : ""}
        {" — contesto "}
        {favorevole ? "favorevole" : sfavorevole ? "sfavorevole" : "neutro"}
        {contesto.gol_fatti_pg != null
          ? ` · ${contesto.gol_fatti_pg} gol fatti e ${contesto.gol_subiti_pg} subiti a partita`
          : ""}
      </p>
      {contesto.motivi?.length ? (
        <ul className={sfavorevole ? "bullets bullets--warn" : "bullets"}>
          {contesto.motivi.map((motivo) => (
            <li key={motivo}>{motivo}</li>
          ))}
        </ul>
      ) : null}
      {avanzate && avanzate.xG != null ? (
        <p className="micro">
          {avanzate.stagione}: {avanzate.gol} gol su {avanzate.xG} xG (
          {avanzate.scarto_gol_xg > 0 ? "+" : ""}
          {avanzate.scarto_gol_xg}) · xA {avanzate.xA} · {avanzate.presenze}{" "}
          presenze
          {avanzate.rating != null
            ? ` · rating ${Number(avanzate.rating).toFixed(2)}`
            : ""}
        </p>
      ) : (
        <p className="micro">
          Statistiche avanzate non disponibili per questa squadra.
        </p>
      )}
    </Disclosure>
  );
}
